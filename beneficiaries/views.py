import re

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
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
    page_size_query_param = "page_size"
    max_page_size = 100


class BeneficiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "last_name",
        "child_number",
        "short_name",
        "village",
        "community_number",
        "participant_case_number",
    ]

    filterset_fields = [
        "gender",
        "sponsorship_status",
        "village",
    ]

    ordering_fields = [
        "child_number",
        "last_name",
        "created_at",
        "birthdate",
        "village",
        "sponsorship_status",
    ]

    ordering = ["-child_number"]

    def get_serializer_class(self):
        if self.action == "list":
            return BeneficiaryListSerializer

        return BeneficiaryDetailSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Beneficiary.objects.select_related(
            "created_by"
        )

        if self.action != "list":
            queryset = queryset.prefetch_related(
                "notes",
                "documents",
                "support_logs",
            )

        is_admin = (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "role", "").lower() == "admin"
        )

        if not is_admin:
            queryset = queryset.filter(
                created_by=user
            )

        return queryset

    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        beneficiary = self.get_object()

        serializer = NoteSerializer(
            data={
                "text": request.data.get("text", ""),
                "author": (
                    request.user.email
                    if request.user.is_authenticated
                    else "Anonymous"
                ),
            }
        )

        if serializer.is_valid():
            serializer.save(
                beneficiary=beneficiary
            )

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=True, methods=["post"])
    def documents(self, request, pk=None):
        beneficiary = self.get_object()

        file = request.FILES.get("file")

        if not file:
            return Response(
                {"error": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document = Document.objects.create(
            beneficiary=beneficiary,
            file=file,
            name=file.name,
            size=file.size,
            type=file.content_type or "",
        )

        serializer = DocumentSerializer(document)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path="documents/(?P<doc_id>[^/.]+)",
    )
    def delete_document(
        self,
        request,
        pk=None,
        doc_id=None,
    ):
        beneficiary = self.get_object()

        try:
            document = Document.objects.get(
                id=doc_id,
                beneficiary=beneficiary,
            )

            document.delete()

            return Response(
                status=status.HTTP_204_NO_CONTENT
            )

        except Document.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"])
    def support(self, request, pk=None):
        beneficiary = self.get_object()

        serializer = SupportLogSerializer(
            data={
                "type": request.data.get(
                    "type",
                    "Cash",
                ),
                "amount": request.data.get(
                    "amount"
                ) or 0,
                "date": request.data.get("date"),
                "notes": request.data.get(
                    "notes",
                    "",
                ),
                "status": request.data.get(
                    "status",
                    "Pending",
                ),
                "logged_by": (
                    request.user.email
                    if request.user.is_authenticated
                    else ""
                ),
            }
        )

        if serializer.is_valid():
            serializer.save(
                beneficiary=beneficiary
            )

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["delete"])
    def clear_all(self, request):
        user = request.user

        is_admin = (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "role", "").lower() == "admin"
        )

        if not is_admin:
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        Beneficiary.objects.all().delete()

        return Response(
            {"message": "All beneficiaries deleted"},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="bulk",
    )
    def bulk(self, request):
        data = request.data

        if not isinstance(data, list):
            return Response(
                {
                    "error": "Expected a list of beneficiaries"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not data:
            return Response(
                {
                    "created_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0,
                    "failed": [],
                },
                status=status.HTTP_200_OK,
            )

        user = request.user

        child_numbers = []

        for item in data:
            if not isinstance(item, dict):
                continue

            value = str(
                item.get("childNumber")
                or item.get("child_number")
                or ""
            ).strip()

            if value:
                child_numbers.append(value)

        existing_numbers = set(
            Beneficiary.objects.filter(
                child_number__in=child_numbers
            ).values_list(
                "child_number",
                flat=True,
            )
        )

        created_count = 0
        skipped_count = 0
        failed_count = 0
        failed_rows = []
        beneficiaries_to_create = []
        seen_numbers = set()

        for idx, item in enumerate(
            data,
            start=1,
        ):
            if not isinstance(item, dict):
                failed_count += 1
                failed_rows.append(
                    {
                        "row": idx,
                        "errors": "Invalid row format.",
                    }
                )
                continue

            child_number = str(
                item.get("childNumber")
                or item.get("child_number")
                or ""
            ).strip()

            if not child_number:
                failed_count += 1
                failed_rows.append(
                    {
                        "row": idx,
                        "errors": {
                            "childNumber": [
                                "This field is required."
                            ]
                        },
                    }
                )
                continue

            if (
                child_number in existing_numbers
                or child_number in seen_numbers
            ):
                skipped_count += 1
                continue

            payload = {
                "community_number": str(
                    item.get("communityNumber")
                    or item.get("community_number")
                    or ""
                ).strip(),
                "last_name": str(
                    item.get("lastName")
                    or item.get("last_name")
                    or ""
                ).strip(),
                "child_number": child_number,
                "participant_case_number": str(
                    item.get("participantCaseNumber")
                    or item.get(
                        "participant_case_number"
                    )
                    or ""
                ).strip(),
                "gender": item.get(
                    "gender"
                ) or "Female",
                "short_name": str(
                    item.get("shortName")
                    or item.get("short_name")
                    or ""
                ).strip(),
                "birthdate": item.get(
                    "birthdate"
                ) or None,
                "age": item.get("age") or None,
                "village": str(
                    item.get("village")
                    or ""
                ).strip(),
                "sponsorship_status": (
                    item.get("sponsorshipStatus")
                    or item.get(
                        "sponsorship_status"
                    )
                    or "Sponsored"
                ),
                "enrollment_date": (
                    item.get("enrollmentDate")
                    or item.get(
                        "enrollment_date"
                    )
                    or None
                ),
                "narrative_date": (
                    item.get("narrativeDate")
                    or item.get(
                        "narrative_date"
                    )
                    or None
                ),
                "photo_date": (
                    item.get("photoDate")
                    or item.get(
                        "photo_date"
                    )
                    or None
                ),
                "created_by": user,
            }

            if not payload["last_name"]:
                failed_count += 1
                failed_rows.append(
                    {
                        "row": idx,
                        "errors": {
                            "lastName": [
                                "This field is required."
                            ]
                        },
                    }
                )
                continue

            try:
                beneficiary = Beneficiary(
                    **payload
                )

                beneficiary.full_clean()

                beneficiaries_to_create.append(
                    beneficiary
                )

                seen_numbers.add(
                    child_number
                )

            except Exception as e:
                failed_count += 1
                failed_rows.append(
                    {
                        "row": idx,
                        "errors": str(e),
                    }
                )

        if beneficiaries_to_create:
            try:
                with transaction.atomic():
                    Beneficiary.objects.bulk_create(
                        beneficiaries_to_create,
                        batch_size=500,
                    )

                created_count = len(
                    beneficiaries_to_create
                )

            except Exception as e:
                created_count = 0
                failed_count += len(
                    beneficiaries_to_create
                )

                failed_rows.append(
                    {
                        "row": "bulk",
                        "errors": str(e),
                    }
                )

        return Response(
            {
                "created_count": created_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
                "failed": failed_rows,
            },
            status=status.HTTP_200_OK,
        )


class SupportLogViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    serializer_class = SupportLogSerializer

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "beneficiary__last_name",
        "beneficiary__short_name",
        "beneficiary__child_number",
        "beneficiary__participant_case_number",
        "beneficiary__community_number",
        "type",
        "notes",
    ]

    filterset_fields = [
        "type",
        "status",
        "beneficiary",
    ]

    ordering_fields = [
        "date",
        "logged_at",
        "amount",
        "type",
        "status",
    ]

    ordering = ["-logged_at"]

    def get_queryset(self):
        user = self.request.user

        queryset = SupportLog.objects.select_related(
            "beneficiary"
        )

        is_admin = (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "role", "").lower() == "admin"
        )

        if not is_admin:
            queryset = queryset.filter(
                logged_by=user.email
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            logged_by=(
                self.request.user.email
                if self.request.user.is_authenticated
                else ""
            )
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="import",
    )
    def import_benefits(self, request):
        data = request.data

        if not isinstance(data, list):
            return Response(
                {
                    "error": (
                        "Expected a list of benefit records."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        beneficiaries = list(
            Beneficiary.objects.all().only(
                "id",
                "last_name",
                "short_name",
                "child_number",
            )
        )

        by_child_number = {}
        by_name = {}

        for beneficiary in beneficiaries:
            child_number = self.normalize_value(
                beneficiary.child_number
            )

            if child_number:
                by_child_number[
                    child_number
                ] = beneficiary

            names = self.get_beneficiary_names(
                beneficiary
            )

            for name in names:
                normalized = self.normalize_name(
                    name
                )

                if normalized:
                    by_name.setdefault(
                        normalized,
                        [],
                    ).append(
                        beneficiary
                    )

        created = 0
        skipped = 0
        missing = []
        ambiguous = []
        failed = []

        with transaction.atomic():
            for index, row in enumerate(
                data,
                start=1,
            ):
                if not isinstance(row, dict):
                    failed.append(
                        {
                            "row": index,
                            "error": "Invalid row format.",
                        }
                    )
                    continue

                name = str(
                    row.get("beneficiaryName")
                    or ""
                ).strip()

                child_number = str(
                    row.get("childNumber")
                    or ""
                ).strip()

                benefit_type = str(
                    row.get("type")
                    or ""
                ).strip()

                amount = row.get(
                    "amount",
                    0,
                )

                date = str(
                    row.get("date")
                    or ""
                ).strip()

                notes = str(
                    row.get("notes")
                    or ""
                ).strip()

                status_value = str(
                    row.get("status")
                    or "Pending"
                ).strip()

                if not name and not child_number:
                    missing.append(
                        {
                            "row": index,
                            "name": "",
                            "childNumber": "",
                            "reason": (
                                "No beneficiary name or "
                                "child number provided."
                            ),
                        }
                    )
                    skipped += 1
                    continue

                if not benefit_type:
                    failed.append(
                        {
                            "row": index,
                            "error": (
                                "Benefit type is required."
                            ),
                        }
                    )
                    continue

                if not date:
                    failed.append(
                        {
                            "row": index,
                            "error": (
                                "Benefit date is required."
                            ),
                        }
                    )
                    continue

                beneficiary = None

                normalized_child_number = (
                    self.normalize_value(
                        child_number
                    )
                )

                if normalized_child_number:
                    beneficiary = (
                        by_child_number.get(
                            normalized_child_number
                        )
                    )

                if not beneficiary and name:
                    normalized_name = (
                        self.normalize_name(
                            name
                        )
                    )

                    candidates = by_name.get(
                        normalized_name,
                        [],
                    )

                    if len(candidates) == 1:
                        beneficiary = candidates[0]

                    elif len(candidates) > 1:
                        ambiguous.append(
                            {
                                "row": index,
                                "name": name,
                                "childNumber": (
                                    child_number
                                ),
                                "reason": (
                                    "Multiple beneficiaries "
                                    "have this name."
                                ),
                            }
                        )
                        skipped += 1
                        continue

                if not beneficiary:
                    missing.append(
                        {
                            "row": index,
                            "name": name,
                            "childNumber": (
                                child_number
                            ),
                            "reason": (
                                "Beneficiary not found."
                            ),
                        }
                    )
                    skipped += 1
                    continue

                try:
                    SupportLog.objects.create(
                        beneficiary=beneficiary,
                        type=benefit_type,
                        amount=amount or 0,
                        date=date,
                        notes=notes,
                        status=(
                            status_value
                            or "Pending"
                        ),
                        logged_by=(
                            request.user.email
                            if request.user.is_authenticated
                            else ""
                        ),
                    )

                    created += 1

                except Exception as e:
                    failed.append(
                        {
                            "row": index,
                            "error": str(e),
                        }
                    )

        return Response(
            {
                "created": created,
                "skipped": skipped,
                "missing": missing,
                "ambiguous": ambiguous,
                "failed": failed,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def normalize_value(value):
        return re.sub(
            r"\s+",
            " ",
            str(value or "").strip().lower(),
        )

    @staticmethod
    def normalize_name(value):
        value = str(
            value or ""
        ).strip().lower()

        value = re.sub(
            r"[^a-z0-9\s]",
            " ",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    @staticmethod
    def get_beneficiary_names(beneficiary):
        names = set()

        short_name = str(
            beneficiary.short_name or ""
        ).strip()

        last_name = str(
            beneficiary.last_name or ""
        ).strip()

        if short_name:
            names.add(short_name)

        if last_name:
            names.add(last_name)

        if short_name and last_name:
            names.add(
                f"{short_name} {last_name}"
            )

            names.add(
                f"{last_name} {short_name}"
            )

        return names


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        is_admin = (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "role", "").lower() == "admin"
        )

        if is_admin:
            beneficiaries = Beneficiary.objects.all()
            support_logs = SupportLog.objects.all()
        else:
            beneficiaries = Beneficiary.objects.filter(
                created_by=user
            )
            support_logs = SupportLog.objects.filter(
                logged_by=user.email
            )

        beneficiary_count = beneficiaries.count()
        total_benefits = support_logs.count()

        benefit_queryset = (
            support_logs
            .values("type")
            .annotate(
                count=Count("id")
            )
            .order_by("-count")
        )

        benefit_types = []

        for item in benefit_queryset:
            count = item["count"]

            percentage = (
                round(
                    (
                        count
                        / total_benefits
                    )
                    * 100,
                    1,
                )
                if total_benefits > 0
                else 0
            )

            benefit_types.append(
                {
                    "type": (
                        item["type"]
                        or "Unknown"
                    ),
                    "count": count,
                    "percentage": percentage,
                }
            )

        employee_stats = []

        if is_admin:
            users = User.objects.filter(
                is_active=True
            ).order_by("email")

            for employee in users:
                count = Beneficiary.objects.filter(
                    created_by=employee
                ).count()

                employee_stats.append(
                    {
                        "email": employee.email,
                        "beneficiary_count": count,
                    }
                )
        else:
            employee_stats.append(
                {
                    "email": user.email,
                    "beneficiary_count": (
                        beneficiary_count
                    ),
                }
            )

        return Response(
            {
                "beneficiary_count": (
                    beneficiary_count
                ),
                "employee_count": (
                    User.objects.filter(
                        is_active=True
                    ).count()
                    if is_admin
                    else 1
                ),
                "total_benefits": (
                    total_benefits
                ),
                "benefit_types": (
                    benefit_types
                ),
                "employee_stats": (
                    employee_stats
                ),
            },
            status=status.HTTP_200_OK,
        )


class EmployeeActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        email = request.query_params.get(
            "email"
        )

        is_admin = (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "role", "").lower() == "admin"
        )

        if is_admin:
            if email:
                employee = User.objects.filter(
                    email__iexact=email
                ).first()

                if not employee:
                    return Response(
                        {
                            "detail": (
                                "Employee not found."
                            )
                        },
                        status=(
                            status.HTTP_404_NOT_FOUND
                        ),
                    )

                beneficiary_count = (
                    Beneficiary.objects.filter(
                        created_by=employee
                    ).count()
                )

                benefit_count = (
                    SupportLog.objects.filter(
                        logged_by=employee.email
                    ).count()
                )

                return Response(
                    {
                        "email": employee.email,
                        "beneficiary_count": (
                            beneficiary_count
                        ),
                        "benefit_count": (
                            benefit_count
                        ),
                    }
                )

            users = User.objects.filter(
                is_active=True
            ).order_by("email")

            results = []

            for employee in users:
                results.append(
                    {
                        "email": employee.email,
                        "beneficiary_count": (
                            Beneficiary.objects.filter(
                                created_by=employee
                            ).count()
                        ),
                        "benefit_count": (
                            SupportLog.objects.filter(
                                logged_by=employee.email
                            ).count()
                        ),
                    }
                )

            return Response(results)

        beneficiary_count = (
            Beneficiary.objects.filter(
                created_by=user
            ).count()
        )

        benefit_count = (
            SupportLog.objects.filter(
                logged_by=user.email
            ).count()
        )

        return Response(
            {
                "email": user.email,
                "beneficiary_count": (
                    beneficiary_count
                ),
                "benefit_count": (
                    benefit_count
                ),
            }
        )
