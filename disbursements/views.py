from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from beneficiaries.models import Beneficiary
from .models import Bursary
from .serializers import BursarySerializer


class BursaryViewSet(ModelViewSet):
    serializer_class = BursarySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Bursary.objects.select_related(
            "beneficiary",
            "created_by"
        ).all()

        search = self.request.query_params.get("search", "").strip()
        zone = self.request.query_params.get("zone", "").strip()
        case_number = self.request.query_params.get("case_number", "").strip()
        admission_number = self.request.query_params.get(
            "admission_number",
            ""
        ).strip()
        beneficiary_name = self.request.query_params.get(
            "beneficiary_name",
            ""
        ).strip()
        school = self.request.query_params.get("school", "").strip()
        grade = self.request.query_params.get("grade", "").strip()
        performance = self.request.query_params.get(
            "performance",
            ""
        ).strip()
        account_number = self.request.query_params.get(
            "account_number",
            ""
        ).strip()
        branch = self.request.query_params.get("branch", "").strip()
        status_filter = self.request.query_params.get(
            "status",
            ""
        ).strip()
        date = self.request.query_params.get("date", "").strip()

        if search:
            queryset = queryset.filter(
                Q(zone__icontains=search)
                | Q(case_number__icontains=search)
                | Q(admission_number__icontains=search)
                | Q(beneficiary_name__icontains=search)
                | Q(school__icontains=search)
                | Q(grade__icontains=search)
                | Q(performance__icontains=search)
                | Q(account_number__icontains=search)
                | Q(branch__icontains=search)
                | Q(notes__icontains=search)
            )

        if zone:
            queryset = queryset.filter(zone__icontains=zone)

        if case_number:
            queryset = queryset.filter(
                case_number__icontains=case_number
            )

        if admission_number:
            queryset = queryset.filter(
                admission_number__icontains=admission_number
            )

        if beneficiary_name:
            queryset = queryset.filter(
                beneficiary_name__icontains=beneficiary_name
            )

        if school:
            queryset = queryset.filter(school__icontains=school)

        if grade:
            queryset = queryset.filter(grade__icontains=grade)

        if performance:
            queryset = queryset.filter(
                performance__icontains=performance
            )

        if account_number:
            queryset = queryset.filter(
                account_number__icontains=account_number
            )

        if branch:
            queryset = queryset.filter(branch__icontains=branch)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if date:
            queryset = queryset.filter(date=date)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(
        detail=False,
        methods=["get"],
        url_path="search"
    )
    def search_bursaries(self, request):
        queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        url_path="import"
    )
    def import_bursaries(self, request):
        rows = request.data

        if not isinstance(rows, list):
            return Response(
                {
                    "error": "Expected a list of bursary records."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        created = 0
        skipped = 0
        errors = []
        missing_beneficiaries = []

        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                skipped += 1
                errors.append({
                    "row": index,
                    "error": "Invalid row format."
                })
                continue

            beneficiary = None

            child_number = str(
                row.get("child_number")
                or row.get("childNumber")
                or ""
            ).strip()

            case_number = str(
                row.get("case_number")
                or row.get("caseNumber")
                or ""
            ).strip()

            admission_number = str(
                row.get("admission_number")
                or row.get("admissionNumber")
                or ""
            ).strip()

            beneficiary_name = str(
                row.get("beneficiary_name")
                or row.get("beneficiaryName")
                or row.get("name")
                or ""
            ).strip()

            if child_number:
                beneficiary = Beneficiary.objects.filter(
                    child_number__iexact=child_number
                ).first()

            if not beneficiary and case_number:
                beneficiary = Beneficiary.objects.filter(
                    participant_case_number__iexact=case_number
                ).first()

            if not beneficiary and beneficiary_name:
                matches = Beneficiary.objects.filter(
                    Q(short_name__iexact=beneficiary_name)
                    | Q(last_name__iexact=beneficiary_name)
                    | Q(full_name__iexact=beneficiary_name)
                )

                if matches.count() == 1:
                    beneficiary = matches.first()

            if not beneficiary:
                missing_beneficiaries.append({
                    "row": index,
                    "name": beneficiary_name,
                    "child_number": child_number,
                    "case_number": case_number,
                })

            try:
                amount = row.get("amount", 0)

                if amount in ("", None):
                    amount = 0

                bursary = Bursary.objects.create(
                    zone=str(
                        row.get("zone") or ""
                    ).strip(),
                    case_number=case_number,
                    admission_number=admission_number,
                    beneficiary_name=beneficiary_name,
                    school=str(
                        row.get("school") or ""
                    ).strip(),
                    grade=str(
                        row.get("grade") or ""
                    ).strip(),
                    performance=str(
                        row.get("performance") or ""
                    ).strip(),
                    account_number=str(
                        row.get("account_number")
                        or row.get("accountNumber")
                        or ""
                    ).strip(),
                    branch=str(
                        row.get("branch") or ""
                    ).strip(),
                    amount=amount,
                    date=row.get("date") or None,
                    status=str(
                        row.get("status")
                        or "Pending"
                    ).strip(),
                    notes=str(
                        row.get("notes") or ""
                    ).strip(),
                    beneficiary=beneficiary,
                    created_by=request.user,
                )

                created += 1

            except Exception as exc:
                skipped += 1
                errors.append({
                    "row": index,
                    "error": str(exc)
                })

        return Response(
            {
                "created": created,
                "skipped": skipped,
                "missing_beneficiaries": missing_beneficiaries,
                "errors": errors,
            },
            status=status.HTTP_201_CREATED
        )