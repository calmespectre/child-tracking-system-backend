from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.db.models import Q, Sum
from django.db import transaction

from .models import (
    Beneficiary,
    Note,
    Document,
    SupportLog,
)

from .serializers import (
    BeneficiaryDetailSerializer,
    BeneficiaryListSerializer,
    NoteSerializer,
    DocumentSerializer,
    SupportLogSerializer,
)

from accounts.permissions import IsAdmin


class BeneficiaryViewSet(viewsets.ModelViewSet):
    queryset = Beneficiary.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in [
            "list",
            "all_beneficiaries",
        ]:
            return BeneficiaryListSerializer

        return BeneficiaryDetailSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Beneficiary.objects.all()

        if user.role == "employee":
            queryset = queryset.filter(
                created_by=user
            )

        search = self.request.query_params.get(
            "search",
            ""
        ).strip()

        status_value = self.request.query_params.get(
            "status",
            ""
        ).strip()

        ordering = self.request.query_params.get(
            "ordering",
            "-child_number"
        )

        if search:
            queryset = queryset.filter(
                Q(last_name__icontains=search)
                | Q(child_number__icontains=search)
                | Q(village__icontains=search)
                | Q(community_number__icontains=search)
                | Q(short_name__icontains=search)
                | Q(participant_case_number__icontains=search)
            )

        if status_value and status_value.lower() != "all":
            queryset = queryset.filter(
                sponsorship_status=status_value
            )

        allowed_ordering = [
            "child_number",
            "-child_number",
            "last_name",
            "-last_name",
            "created_at",
            "-created_at",
        ]

        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by("-child_number")

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset()
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = BeneficiaryListSerializer(
                page,
                many=True,
                context={
                    "request": request
                },
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = BeneficiaryListSerializer(
            queryset,
            many=True,
            context={
                "request": request
            },
        )

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        beneficiary = self.get_object()

        beneficiary = (
            Beneficiary.objects
            .select_related("created_by")
            .prefetch_related(
                "notes",
                "documents",
                "support_logs",
            )
            .get(pk=beneficiary.pk)
        )

        serializer = BeneficiaryDetailSerializer(
            beneficiary,
            context={
                "request": request
            },
        )

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="benefits",
    )
    def benefits(self, request):
        user = request.user

        queryset = SupportLog.objects.select_related(
            "beneficiary"
        )

        if user.role == "employee":
            queryset = queryset.filter(
                beneficiary__created_by=user
            )

        search = request.query_params.get(
            "search",
            ""
        ).strip()

        benefit_type = request.query_params.get(
            "type",
            ""
        ).strip()

        ordering = request.query_params.get(
            "ordering",
            "-date"
        ).strip()

        if search:
            queryset = queryset.filter(
                Q(beneficiary__short_name__icontains=search)
                | Q(beneficiary__last_name__icontains=search)
                | Q(beneficiary__child_number__icontains=search)
                | Q(type__icontains=search)
                | Q(notes__icontains=search)
            )

        if benefit_type and benefit_type.lower() != "all":
            queryset = queryset.filter(
                type=benefit_type
            )

        allowed_ordering = [
            "date",
            "-date",
            "logged_at",
            "-logged_at",
            "type",
            "-type",
        ]

        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by("-date", "-logged_at")

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = SupportLogSerializer(
                page,
                many=True,
                context={
                    "request": request
                },
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = SupportLogSerializer(
            queryset,
            many=True,
            context={
                "request": request
            },
        )

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        url_path="benefits/import",
    )
    def import_benefits(self, request):
        data = request.data

        if not isinstance(data, list):
            return Response(
                {
                    "error": "Expected a list of benefit records."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not data:
            return Response(
                {
                    "created": 0,
                    "skipped": 0,
                    "missing": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        beneficiaries = Beneficiary.objects.all()

        if user.role == "employee":
            beneficiaries = beneficiaries.filter(
                created_by=user
            )

        beneficiaries = beneficiaries.only(
            "id",
            "last_name",
            "short_name",
            "child_number",
        )

        name_map = {}

        for beneficiary in beneficiaries:
            names = {
                beneficiary.short_name,
                beneficiary.last_name,
            }

            for name in names:
                if name:
                    key = name.strip().lower()

                    if key not in name_map:
                        name_map[key] = beneficiary

        created = 0
        skipped = 0
        missing = []

        support_logs = []

        for row in data:
            beneficiary_name = str(
                row.get("beneficiaryName", "")
            ).strip()

            benefit_type = str(
                row.get("type", "")
            ).strip()

            date = str(
                row.get("date", "")
            ).strip()

            notes = str(
                row.get("notes", "")
            ).strip()

            amount = row.get(
                "amount",
                0
            )

            status_value = str(
                row.get("status", "Pending")
            ).strip() or "Pending"

            if not beneficiary_name or not benefit_type or not date:
                skipped += 1
                continue

            beneficiary = name_map.get(
                beneficiary_name.lower()
            )

            if not beneficiary:
                skipped += 1

                if beneficiary_name not in missing:
                    missing.append(
                        beneficiary_name
                    )

                continue

            try:
                amount = float(amount or 0)
            except (TypeError, ValueError):
                amount = 0

            support_logs.append(
                SupportLog(
                    beneficiary=beneficiary,
                    type=benefit_type,
                    amount=amount,
                    date=date,
                    notes=notes,
                    status=status_value,
                    logged_by=(
                        user.email
                        if user.is_authenticated
                        else ""
                    ),
                )
            )

            created += 1

        with transaction.atomic():
            SupportLog.objects.bulk_create(
                support_logs,
                batch_size=1000,
            )

        return Response(
            {
                "created": created,
                "skipped": skipped,
                "missing": missing,
                "message": (
                    f"{created} benefit records imported successfully."
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="support",
    )
    def log_support(
        self,
        request,
        pk=None,
    ):
        beneficiary = self.get_object()

        data = request.data.copy()

        serializer = SupportLogSerializer(
            data=data
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save(
            beneficiary=beneficiary,
            logged_by=(
                request.user.email
                if request.user.is_authenticated
                else ""
            ),
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="bulk",
    )
    def bulk_create(self, request):
        data = request.data

        if not isinstance(data, list):
            return Response(
                {
                    "error": "Expected a list of objects."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not data:
            return Response(
                {
                    "created": [],
                    "skipped": 0,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        seen = set()
        unique_data = []

        for item in data:
            child_number = item.get(
                "childNumber"
            )

            if not child_number:
                continue

            child_number = str(
                child_number
            ).strip()

            if child_number not in seen:
                seen.add(child_number)
                unique_data.append(item)

        incoming_numbers = [
            item.get("childNumber")
            for item in unique_data
            if item.get("childNumber")
        ]

        existing = set(
            Beneficiary.objects.filter(
                child_number__in=incoming_numbers
            ).values_list(
                "child_number",
                flat=True,
            )
        )

        to_create = [
            item
            for item in unique_data
            if item.get("childNumber")
            not in existing
        ]

        skipped = (
            len(data)
            - len(to_create)
        )

        if not to_create:
            return Response(
                {
                    "created": [],
                    "skipped": skipped,
                    "message": "No new beneficiaries to create.",
                },
                status=status.HTTP_201_CREATED,
            )

        serializer = BeneficiaryDetailSerializer(
            data=to_create,
            many=True,
            context={
                "request": request
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        with transaction.atomic():
            serializer.save()

        return Response(
            {
                "created": serializer.data,
                "skipped": skipped,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="all",
    )
    def all_beneficiaries(self, request):
        queryset = self.filter_queryset(
            self.get_queryset()
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = BeneficiaryListSerializer(
                page,
                many=True,
                context={
                    "request": request
                },
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = BeneficiaryListSerializer(
            queryset,
            many=True,
            context={
                "request": request
            },
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="notes",
    )
    def add_note(
        self,
        request,
        pk=None,
    ):
        beneficiary = self.get_object()

        serializer = NoteSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save(
            beneficiary=beneficiary
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="documents",
    )
    def upload_document(
        self,
        request,
        pk=None,
    ):
        beneficiary = self.get_object()

        file = request.FILES.get("file")

        if not file:
            return Response(
                {
                    "error": "No file provided."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        document = Document.objects.create(
            beneficiary=beneficiary,
            file=file,
            name=file.name,
            size=file.size,
            type=file.content_type or "",
        )

        serializer = DocumentSerializer(
            document,
            context={
                "request": request
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"documents/(?P<doc_id>[^/.]+)",
    )
    def delete_document(
        self,
        request,
        pk=None,
        doc_id=None,
    ):
        beneficiary = self.get_object()

        try:
            document = beneficiary.documents.get(
                id=doc_id
            )
        except Document.DoesNotExist:
            return Response(
                {
                    "error": "Document not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        document.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )

    @action(
        detail=False,
        methods=["delete"],
        url_path="clear_all",
        permission_classes=[
            IsAuthenticated,
            IsAdmin,
        ],
    )
    def clear_all(
        self,
        request,
    ):
        Beneficiary.objects.all().delete()

        return Response(
            {
                "message": "All beneficiaries deleted."
            },
            status=status.HTTP_204_NO_CONTENT,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="summary",
    )
    def summary(
        self,
        request,
    ):
        user = request.user

        queryset = Beneficiary.objects.all()

        if user.role == "employee":
            queryset = queryset.filter(
                created_by=user
            )

        beneficiary_count = queryset.count()

        logs = SupportLog.objects.filter(
            beneficiary__in=queryset
        )

        pending_disbursements = logs.filter(
            status="Pending"
        ).count()

        total_support = (
            logs.aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        return Response(
            {
                "beneficiary_count": beneficiary_count,
                "pending_disbursements": pending_disbursements,
                "total_support": total_support,
            }
        )
