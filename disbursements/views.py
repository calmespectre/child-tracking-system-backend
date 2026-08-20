from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
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

    filter_backends = [
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = [
        "zone",
        "case_number",
        "admission_number",
        "name",
        "school",
        "grade",
        "performance",
        "account_number",
        "branch",
    ]

    ordering_fields = [
        "id",
        "created_at",
        "updated_at",
        "name",
        "zone",
        "school",
        "grade",
        "amount",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):
        return Bursary.objects.all()

    @action(detail=False, methods=["post"], url_path="import")
    def import_bursaries(self, request):
        rows = request.data

        if not isinstance(rows, list):
            return Response(
                {"detail": "Expected a list of bursary records."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = 0
        skipped = 0
        errors = []

        for index, row in enumerate(rows, start=1):
            try:
                Bursary.objects.create(
                    zone=str(row.get("zone", "")).strip(),
                    case_number=str(row.get("case_number", "")).strip(),
                    admission_number=str(
                        row.get("admission_number", "")
                    ).strip(),
                    name=str(row.get("name", "")).strip(),
                    school=str(row.get("school", "")).strip(),
                    grade=str(row.get("grade", "")).strip(),
                    performance=str(row.get("performance", "")).strip(),
                    account_number=str(
                        row.get("account_number", "")
                    ).strip(),
                    branch=str(row.get("branch", "")).strip(),
                    amount=row.get("amount", 0) or 0,
                )

                created += 1

            except Exception as exc:
                skipped += 1
                errors.append(
                    {
                        "row": index,
                        "error": str(exc),
                    }
                )

        return Response(
            {
                "created": created,
                "skipped": skipped,
                "errors": errors,
            },
            status=status.HTTP_201_CREATED,
        )
