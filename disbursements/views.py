from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import PageNumberPagination
from .models import Bursary
from .serializers import BursarySerializer


class BursaryPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class BursaryViewSet(ModelViewSet):
    serializer_class = BursarySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = BursaryPagination
    filter_backends = [OrderingFilter]
    ordering_fields = [
        "id", "created_at", "updated_at", "beneficiary_name",
        "zone", "case_number", "admission_number", "school",
        "grade", "performance", "account_number", "branch",
        "amount", "date", "status"
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Bursary.objects.all()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(beneficiary_name__icontains=search) |
                Q(case_number__icontains=search) |
                Q(admission_number__icontains=search) |
                Q(school__icontains=search)
            )
        return queryset

    @action(detail=False, methods=["post"], url_path="import")
    def import_bursaries(self, request):
        rows = request.data
        if not isinstance(rows, list):
            return Response(
                {"detail": "Expected a list of bursary records."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        created = 0
        errors = []
        for index, row in enumerate(rows, start=1):
            try:
                if not isinstance(row, dict):
                    raise ValueError("Each row must be an object.")
                beneficiary_name = row.get(
                    "beneficiary_name") or row.get("name") or ""
                if not beneficiary_name:
                    raise ValueError("Beneficiary name is required.")
                Bursary.objects.create(
                    zone=row.get("zone", ""),
                    case_number=row.get("case_number") or row.get(
                        "caseNumber") or "",
                    admission_number=row.get("admission_number") or row.get(
                        "admissionNumber") or "",
                    beneficiary_name=beneficiary_name,
                    school=row.get("school", ""),
                    grade=row.get("grade", ""),
                    performance=row.get("performance", ""),
                    account_number=row.get("account_number") or row.get(
                        "accountNumber") or "",
                    branch=row.get("branch", ""),
                    amount=float(row.get("amount", 0)),
                    date=row.get("date") or None,
                    status=row.get("status", "Pending"),
                    notes=row.get("notes", ""),
                )
                created += 1
            except Exception as e:
                errors.append({"row": index, "error": str(e)})
        return Response(
            {"created": created, "errors": errors},
            status=status.HTTP_201_CREATED if created > 0 else status.HTTP_400_BAD_REQUEST,
        )
