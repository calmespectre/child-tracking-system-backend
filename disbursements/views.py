from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import PageNumberPagination
from .models import Disbursement
from .serializers import DisbursementSerializer


class DisbursementPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class DisbursementViewSet(ModelViewSet):
    serializer_class = DisbursementSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DisbursementPagination
    filter_backends = [OrderingFilter]
    ordering_fields = [
        "id", "created_at", "updated_at", "beneficiary_name",
        "zone", "case_number", "admission_number", "school",
        "grade", "performance", "account_number", "branch",
        "amount", "date", "status"
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        program = self.kwargs.get('program')
        if not program:
            return Disbursement.objects.none()
        queryset = Disbursement.objects.filter(program=program)
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(beneficiary_name__icontains=search) |
                Q(case_number__icontains=search) |
                Q(admission_number__icontains=search) |
                Q(school__icontains=search) |
                Q(location__icontains=search) |
                Q(description__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["post"], url_path="import")
    def import_bursaries(self, request, program=None):
        program = self.kwargs.get('program')
        if not program:
            return Response({"detail": "Program not specified."}, status=status.HTTP_400_BAD_REQUEST)
        rows = request.data
        if not isinstance(rows, list):
            return Response(
                {"detail": "Expected a list of disbursement records."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        created = 0
        errors = []
        for index, row in enumerate(rows, start=1):
            try:
                if not isinstance(row, dict):
                    raise ValueError("Each row must be an object.")
                data = {
                    'program': program,
                    'zone': row.get('zone', ''),
                    'case_number': row.get('case_number', ''),
                    'admission_number': row.get('admission_number', ''),
                    'beneficiary_name': row.get('beneficiary_name', '') or row.get('name', ''),
                    'school': row.get('school', ''),
                    'grade': row.get('grade', ''),
                    'performance': row.get('performance', ''),
                    'account_number': row.get('account_number', ''),
                    'branch': row.get('branch', ''),
                    'location': row.get('location', ''),
                    'description': row.get('description', ''),
                    'quantity': int(row.get('quantity', 0)),
                    'amount': float(row.get('amount', 0)),
                    'date': row.get('date') or None,
                    'status': row.get('status', 'Pending'),
                    'notes': row.get('notes', ''),
                }
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                serializer.save(created_by=self.request.user)
                created += 1
            except Exception as e:
                errors.append({"row": index, "error": str(e)})
        return Response(
            {"created": created, "errors": errors},
            status=status.HTTP_201_CREATED if created > 0 else status.HTTP_400_BAD_REQUEST,
        )
