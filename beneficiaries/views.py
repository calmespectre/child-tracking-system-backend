from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

from .models import Beneficiary, Note, Document, SupportLog
from .serializers import (
    BeneficiaryListSerializer,
    BeneficiaryDetailSerializer,
    NoteSerializer,
    DocumentSerializer,
    SupportLogSerializer,
)

User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class BeneficiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['last_name', 'child_number', 'short_name',
                     'village', 'community_number', 'participant_case_number']
    ordering_fields = ['child_number', 'last_name',
                       'created_at', 'birthdate', 'village', 'sponsorship_status']
    ordering = ['-child_number']

    def get_serializer_class(self):
        if self.action == 'list':
            return BeneficiaryListSerializer
        return BeneficiaryDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Beneficiary.objects.select_related(
            'created_by').prefetch_related('notes', 'documents', 'support_logs')

        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(sponsorship_status=status_param)

        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)):
            queryset = queryset.filter(created_by=user)

        return queryset

    @action(detail=True, methods=['post'])
    def notes(self, request, pk=None):
        beneficiary = self.get_object()
        serializer = NoteSerializer(data={
            'text': request.data.get('text', ''),
            'author': request.user.email if request.user.is_authenticated else 'Anonymous'
        })
        if serializer.is_valid():
            serializer.save(beneficiary=beneficiary)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def documents(self, request, pk=None):
        beneficiary = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        document = Document.objects.create(
            beneficiary=beneficiary,
            file=file,
            name=file.name,
            size=file.size,
            type=file.content_type or ''
        )
        serializer = DocumentSerializer(document)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='documents/(?P<doc_id>[^/.]+)')
    def delete_document(self, request, pk=None, doc_id=None):
        beneficiary = self.get_object()
        try:
            document = Document.objects.get(id=doc_id, beneficiary=beneficiary)
            document.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def support(self, request, pk=None):
        beneficiary = self.get_object()
        serializer = SupportLogSerializer(data={
            'type': request.data.get('type', 'Cash'),
            'amount': request.data.get('amount', 0),
            'date': request.data.get('date'),
            'notes': request.data.get('notes', ''),
            'logged_by': request.user.email if request.user.is_authenticated else ''
        })
        if serializer.is_valid():
            serializer.save(beneficiary=beneficiary)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['delete'])
    def clear_all(self, request):
        user = request.user
        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        Beneficiary.objects.all().delete()
        return Response({'message': 'All beneficiaries deleted'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response({'error': 'Expected a list of beneficiaries'}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        skipped_count = 0
        failed_count = 0
        failed_rows = []

        for idx, item in enumerate(data):
            try:
                child_number = item.get('child_number', '')
                if Beneficiary.objects.filter(child_number=child_number).exists():
                    skipped_count += 1
                    continue

                serializer = BeneficiaryDetailSerializer(
                    data=item, context={'request': request})
                if serializer.is_valid():
                    serializer.save()
                    created_count += 1
                else:
                    failed_count += 1
                    failed_rows.append(
                        {'row': idx + 1, 'errors': serializer.errors})
            except Exception as e:
                failed_count += 1
                failed_rows.append({'row': idx + 1, 'errors': str(e)})

        return Response({
            'created_count': created_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'failed': failed_rows
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def all(self, request):
        user = request.user
        queryset = self.get_queryset()

        status_param = request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(sponsorship_status=status_param)

        search_param = request.query_params.get('search', None)
        if search_param:
            queryset = queryset.filter(
                Q(last_name__icontains=search_param) |
                Q(child_number__icontains=search_param) |
                Q(short_name__icontains=search_param) |
                Q(village__icontains=search_param) |
                Q(community_number__icontains=search_param) |
                Q(participant_case_number__icontains=search_param)
            )

        serializer = BeneficiaryListSerializer(queryset, many=True)
        return Response(serializer.data)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = getattr(user, 'is_staff', False) or getattr(
            user, 'is_superuser', False) or getattr(user, 'role', '').lower() == 'admin'

        if is_admin:
            beneficiaries = Beneficiary.objects.all()
            support_logs = SupportLog.objects.all()
        else:
            beneficiaries = Beneficiary.objects.filter(created_by=user)
            support_logs = SupportLog.objects.filter(logged_by=user.email)

        beneficiary_count = beneficiaries.count()
        total_benefits = support_logs.count()

        benefit_queryset = support_logs.values('type').annotate(
            count=Count('id')).order_by('-count')
        benefit_types = []
        for item in benefit_queryset:
            count = item['count']
            percentage = round((count / total_benefits) * 100,
                               1) if total_benefits > 0 else 0
            benefit_types.append({
                'type': item['type'] or 'Unknown',
                'count': count,
                'percentage': percentage
            })

        employee_stats = []
        if is_admin:
            users = User.objects.filter(is_active=True).order_by('email')
            for employee in users:
                count = Beneficiary.objects.filter(created_by=employee).count()
                employee_stats.append(
                    {'email': employee.email, 'beneficiary_count': count})
        else:
            employee_stats.append(
                {'email': user.email, 'beneficiary_count': beneficiary_count})

        return Response({
            'beneficiary_count': beneficiary_count,
            'employee_count': User.objects.filter(is_active=True).count() if is_admin else 1,
            'total_benefits': total_benefits,
            'benefit_types': benefit_types,
            'employee_stats': employee_stats
        }, status=status.HTTP_200_OK)


class EmployeeActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        email = request.query_params.get('email')
        is_admin = getattr(user, 'is_staff', False) or getattr(
            user, 'is_superuser', False) or getattr(user, 'role', '').lower() == 'admin'

        if is_admin:
            if email:
                employee = User.objects.filter(email__iexact=email).first()
                if not employee:
                    return Response({'detail': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)

                beneficiary_count = Beneficiary.objects.filter(
                    created_by=employee).count()
                benefit_count = SupportLog.objects.filter(
                    logged_by=employee.email).count()
                return Response({
                    'email': employee.email,
                    'beneficiary_count': beneficiary_count,
                    'benefit_count': benefit_count
                })

            users = User.objects.filter(is_active=True).order_by('email')
            results = []
            for employee in users:
                results.append({
                    'email': employee.email,
                    'beneficiary_count': Beneficiary.objects.filter(created_by=employee).count(),
                    'benefit_count': SupportLog.objects.filter(logged_by=employee.email).count()
                })
            return Response(results)

        beneficiary_count = Beneficiary.objects.filter(created_by=user).count()
        benefit_count = SupportLog.objects.filter(logged_by=user.email).count()
        return Response({
            'email': user.email,
            'beneficiary_count': beneficiary_count,
            'benefit_count': benefit_count
        })
