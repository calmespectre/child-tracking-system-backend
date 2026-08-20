from django.db import transaction
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Beneficiary, Document
from .serializers import (
    BeneficiaryListSerializer,
    BeneficiaryDetailSerializer,
    DocumentSerializer,
    NoteSerializer,
    SupportLogSerializer,
)


class BeneficiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

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
        "document_count",
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

        if self.action == "list":
            queryset = queryset.annotate(
                document_count=Count(
                    "documents",
                    distinct=True,
                )
            )
        else:
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

        status_filter = self.request.query_params.get("status")

        if status_filter:
            queryset = queryset.filter(
                sponsorship_status=status_filter
            )

        document_filter = self.request.query_params.get("documents")

        if document_filter == "uploaded":
            queryset = queryset.filter(
                document_count__gt=0
            )

        elif document_filter == "missing":
            queryset = queryset.filter(
                document_count=0
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

        return Response(
            DocumentSerializer(document).data,
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
                "beneficiary": beneficiary.id,
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
            },
            context={
                "request": request
            },
        )

        if serializer.is_valid():
            serializer.save(
                logged_by=(
                    request.user.email
                    if request.user.is_authenticated
                    else ""
                )
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

        deleted_count, _ = (
            Beneficiary.objects.all().delete()
        )

        return Response(
            {
                "message": "All beneficiaries deleted",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        data = request.data

        if not isinstance(data, list):
            return Response(
                {
                    "error": (
                        "Expected a list of beneficiaries"
                    )
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

        child_numbers = [
            str(
                item.get(
                    "childNumber",
                    item.get(
                        "child_number",
                        "",
                    ),
                )
            ).strip()
            for item in data
            if isinstance(item, dict)
            and str(
                item.get(
                    "childNumber",
                    item.get(
                        "child_number",
                        "",
                    ),
                )
                or ""
            ).strip()
        ]

        existing_numbers = set(
            Beneficiary.objects.filter(
                child_number__in=child_numbers
            ).values_list(
                "child_number",
                flat=True,
            )
        )

        objects = []
        failed_rows = []
        skipped_count = 0
        seen_numbers = set()

        for idx, item in enumerate(
            data,
            start=1,
        ):
            if not isinstance(item, dict):
                failed_rows.append(
                    {
                        "row": idx,
                        "errors": (
                            "Invalid row format."
                        ),
                    }
                )
                continue

            child_number = str(
                item.get(
                    "childNumber",
                    item.get(
                        "child_number",
                        "",
                    ),
                )
                or ""
            ).strip()

            if not child_number:
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

            if child_number in existing_numbers:
                skipped_count += 1
                continue

            if child_number in seen_numbers:
                skipped_count += 1
                continue

            seen_numbers.add(child_number)

            try:
                last_name = str(
                    item.get(
                        "lastName",
                        item.get(
                            "last_name",
                            "",
                        ),
                    )
                    or ""
                ).strip()

                if not last_name:
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

                gender = str(
                    item.get(
                        "gender",
                        "Female",
                    )
                    or "Female"
                ).strip()

                short_name = str(
                    item.get(
                        "shortName",
                        item.get(
                            "short_name",
                            "",
                        ),
                    )
                    or ""
                ).strip()

                community_number = str(
                    item.get(
                        "communityNumber",
                        item.get(
                            "community_number",
                            "",
                        ),
                    )
                    or ""
                ).strip()

                participant_case_number = str(
                    item.get(
                        "participantCaseNumber",
                        item.get(
                            "participant_case_number",
                            "",
                        ),
                    )
                    or ""
                ).strip()

                village = str(
                    item.get(
                        "village",
                        "",
                    )
                    or ""
                ).strip()

                sponsorship_status = str(
                    item.get(
                        "sponsorshipStatus",
                        item.get(
                            "sponsorship_status",
                            "Sponsored",
                        ),
                    )
                    or "Sponsored"
                ).strip()

                birthdate = item.get(
                    "birthdate"
                )

                enrollment_date = item.get(
                    "enrollmentDate",
                    item.get(
                        "enrollment_date"
                    ),
                )

                narrative_date = item.get(
                    "narrativeDate",
                    item.get(
                        "narrative_date"
                    ),
                )

                photo_date = item.get(
                    "photoDate",
                    item.get(
                        "photo_date"
                    ),
                )

                age = item.get("age")

                objects.append(
                    Beneficiary(
                        community_number=community_number,
                        last_name=last_name,
                        child_number=child_number,
                        participant_case_number=participant_case_number,
                        gender=gender or "Female",
                        short_name=short_name,
                        birthdate=birthdate or None,
                        age=(
                            age
                            if age not in (
                                "",
                                None,
                            )
                            else None
                        ),
                        village=village,
                        sponsorship_status=(
                            sponsorship_status
                            or "Sponsored"
                        ),
                        enrollment_date=(
                            enrollment_date
                            or None
                        ),
                        narrative_date=(
                            narrative_date
                            or None
                        ),
                        photo_date=(
                            photo_date
                            or None
                        ),
                        created_by=user,
                    )
                )

            except Exception as exc:
                failed_rows.append(
                    {
                        "row": idx,
                        "errors": str(exc),
                    }
                )

        created_count = 0

        if objects:
            try:
                with transaction.atomic():
                    created = (
                        Beneficiary.objects.bulk_create(
                            objects,
                            batch_size=500,
                            ignore_conflicts=True,
                        )
                    )

                    created_count = len(created)

            except Exception as exc:
                return Response(
                    {
                        "created_count": 0,
                        "skipped_count": skipped_count,
                        "failed_count": len(data),
                        "failed": [
                            {
                                "row": 0,
                                "errors": str(exc),
                            }
                        ],
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        failed_count = len(failed_rows)

        return Response(
            {
                "created_count": created_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
                "failed": failed_rows,
            },
            status=status.HTTP_200_OK,
        )
