# views.py
from django.db.models import Count, Avg
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from .models import Beneficiary, Guardian, Document, Note
from .serializers import (
    BeneficiarySerializer, BeneficiaryListSerializer,
    GuardianSerializer, DocumentSerializer, NoteSerializer
)
import traceback


class BeneficiaryPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class BeneficiaryViewSet(viewsets.ModelViewSet):
    queryset = Beneficiary.objects.all()
    serializer_class = BeneficiarySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = BeneficiaryPagination
    filter_backends = [DjangoFilterBackend,
                       filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['gender', 'sponsorship_status', 'community_number']
    search_fields = ['child_number', 'last_name', 'village', 'short_name']
    ordering_fields = ['created_at', 'last_name',
                       'child_number', 'birthdate', 'enrollment_date']
    ordering = ['-created_at']

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            print(traceback.format_exc())
            return Response(
                {'detail': f'Error retrieving beneficiary: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_serializer_class(self):
        if self.action == 'list':
            return BeneficiaryListSerializer
        return BeneficiarySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        doc_filter = self.request.query_params.get('documents')
        if doc_filter == 'uploaded':
            queryset = queryset.annotate(doc_count=Count(
                'documents')).filter(doc_count__gt=0)
        elif doc_filter == 'missing':
            queryset = queryset.annotate(
                doc_count=Count('documents')).filter(doc_count=0)
        return queryset

    @action(detail=True, methods=['get'], url_path='siblings')
    def siblings(self, request, pk=None):
        beneficiary = self.get_object()
        guardian_ids = beneficiary.guardians.values_list('id', flat=True)
        if not guardian_ids:
            return Response([], status=status.HTTP_200_OK)
        sibling_beneficiaries = Beneficiary.objects.filter(
            guardians__id__in=guardian_ids
        ).exclude(id=beneficiary.id).distinct()
        serializer = BeneficiaryListSerializer(
            sibling_beneficiaries, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='import-guardians')
    def import_guardians(self, request):
        confirm = request.query_params.get(
            'confirm', 'false').lower() == 'true'
        rows = request.data
        if not isinstance(rows, list):
            return Response({'detail': 'Expected a list of guardian records.'}, status=status.HTTP_400_BAD_REQUEST)

        results = []
        matched = 0
        unmatched = 0
        duplicates = 0
        invalid = 0

        for row in rows:
            child_number = row.get('child_number', '').strip()
            name = row.get('name', '').strip()
            relationship = row.get('relationship', '').strip()

            if not child_number or not name or not relationship:
                invalid += 1
                results.append({'child_number': child_number,
                               'status': 'invalid', 'reason': 'Missing required fields'})
                continue

            try:
                beneficiary = Beneficiary.objects.get(
                    child_number=child_number)
            except Beneficiary.DoesNotExist:
                unmatched += 1
                results.append({'child_number': child_number,
                               'status': 'unmatched', 'reason': 'Beneficiary not found'})
                continue

            guardian_data = {
                'name': name,
                'relationship': relationship,
                'phone': row.get('phone', ''),
                'email': row.get('email', ''),
                'address': row.get('address', ''),
                'id_number': row.get('id_number', ''),
                'notes': row.get('notes', ''),
            }

            if confirm:
                existing = Guardian.objects.filter(
                    beneficiary=beneficiary,
                    name__iexact=name,
                    relationship__iexact=relationship
                ).first()
                if existing:
                    duplicates += 1
                    results.append({
                        'child_number': child_number,
                        'status': 'duplicate',
                        'guardian': name,
                        'reason': 'Guardian already exists'
                    })
                    continue

                Guardian.objects.create(
                    beneficiary=beneficiary, **guardian_data)
                matched += 1
                results.append({
                    'child_number': child_number,
                    'status': 'matched',
                    'guardian': name,
                    'beneficiary_name': beneficiary.last_name
                })
            else:
                matched += 1
                results.append({
                    'child_number': child_number,
                    'status': 'matched',
                    'guardian': name,
                    'beneficiary_name': beneficiary.last_name
                })

        response_data = {
            'total_rows': len(rows),
            'matched': matched,
            'unmatched': unmatched,
            'duplicates': duplicates,
            'invalid': invalid,
            'rows': results,
        }
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='clear_all')
    def clear_all(self, request):
        count = Beneficiary.objects.count()
        Beneficiary.objects.all().delete()
        return Response({'deleted': count}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_create(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response({'detail': 'Expected a list of beneficiaries.'}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        skipped_count = 0
        failed_count = 0
        failed_rows = []

        for idx, item in enumerate(data):
            try:
                child_number = item.get('child_number')
                if not child_number:
                    failed_count += 1
                    failed_rows.append(
                        {'row': idx, 'error': 'Missing child_number'})
                    continue

                if Beneficiary.objects.filter(child_number=child_number).exists():
                    skipped_count += 1
                    continue

                beneficiary_data = {
                    'community_number': item.get('community_number', ''),
                    'last_name': item.get('last_name', ''),
                    'child_number': child_number,
                    'participant_case_number': item.get('participant_case_number', ''),
                    'gender': item.get('gender', 'Female'),
                    'short_name': item.get('short_name', ''),
                    'birthdate': item.get('birthdate'),
                    'sponsorship_status': item.get('sponsorship_status', 'Sponsored'),
                    'enrollment_date': item.get('enrollment_date'),
                    'narrative_date': item.get('narrative_date'),
                    'photo_date': item.get('photo_date'),
                    'age': item.get('age'),
                    'village': item.get('village', ''),
                }

                for key in ['birthdate', 'enrollment_date', 'narrative_date', 'photo_date', 'age']:
                    if beneficiary_data.get(key) is None:
                        del beneficiary_data[key]

                if not beneficiary_data.get('last_name'):
                    beneficiary_data['last_name'] = 'Unknown'

                Beneficiary.objects.create(**beneficiary_data)
                created_count += 1

            except Exception as e:
                failed_count += 1
                failed_rows.append({'row': idx, 'error': str(e)})

        return Response({
            'created_count': created_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'failed': failed_rows
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='notes')
    def add_note(self, request, pk=None):
        beneficiary = self.get_object()
        text = request.data.get('text')
        if not text:
            return Response({'detail': 'Text is required.'}, status=status.HTTP_400_BAD_REQUEST)
        note = Note.objects.create(
            beneficiary=beneficiary,
            author=request.user,
            text=text
        )
        serializer = NoteSerializer(note)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='documents')
    def upload_document(self, request, pk=None):
        beneficiary = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'File is required.'}, status=status.HTTP_400_BAD_REQUEST)
        doc = Document.objects.create(
            beneficiary=beneficiary,
            name=file.name,
            file=file,
            type=file.content_type,
            size=file.size
        )
        serializer = DocumentSerializer(doc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='documents/(?P<doc_id>[^/.]+)')
    def delete_document(self, request, pk=None, doc_id=None):
        beneficiary = self.get_object()
        try:
            doc = beneficiary.documents.get(id=doc_id)
            doc.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Document.DoesNotExist:
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='guardians')
    def create_guardian(self, request, pk=None):
        beneficiary = self.get_object()
        serializer = GuardianSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(beneficiary=beneficiary)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        total = Beneficiary.objects.count()
        active = Beneficiary.objects.filter(
            sponsorship_status='Sponsored').count()
        gender_breakdown = {
            'female': Beneficiary.objects.filter(gender='Female').count(),
            'male': Beneficiary.objects.filter(gender='Male').count(),
        }

        benefit_types = []
        total_benefits = 0
        try:
            from disbursements.models import Bursary
            bursary_count = Bursary.objects.count()
            if bursary_count > 0:
                benefit_types.append(
                    {'type': 'Bursaries', 'count': bursary_count, 'percentage': 0})
                total_benefits += bursary_count
        except ImportError:
            pass

        from accounts.models import User
        employees = User.objects.filter(role='employee')
        employee_stats = []
        for emp in employees:
            count = Beneficiary.objects.filter(created_by=emp).count()
            if count > 0:
                employee_stats.append({
                    'email': emp.email,
                    'beneficiary_count': count
                })

        avg_age = Beneficiary.objects.exclude(
            age__isnull=True).aggregate(Avg('age'))['age__avg']

        if total > 0 and benefit_types:
            for b in benefit_types:
                b['percentage'] = round(
                    (b['count'] / total_benefits) * 100, 1) if total_benefits else 0

        return Response({
            'beneficiary_count': total,
            'active_beneficiaries': active,
            'gender_breakdown': gender_breakdown,
            'benefit_types': benefit_types,
            'total_benefits': total_benefits,
            'employee_stats': employee_stats,
            'employee_count': employees.count(),
            'average_age': avg_age,
            'total_amount': 0,
        })


class EmployeeActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response({'detail': 'Email parameter required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from accounts.models import User
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'email': email,
            'beneficiary_count': Beneficiary.objects.filter(created_by=user).count(),
            'activities': []
        })


class GuardianViewSet(viewsets.ModelViewSet):
    queryset = Guardian.objects.all()
    serializer_class = GuardianSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'phone', 'email']
