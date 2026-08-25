import os
import re
from datetime import datetime, timedelta

from django.db import models
from django.db.models import Q, Count, Sum
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend

from .models import Beneficiary, Note, Document, SupportLog, Guardian
from .serializers import (
    BeneficiaryListSerializer,
    BeneficiaryDetailSerializer,
    NoteSerializer,
    DocumentSerializer,
    SupportLogSerializer,
    GuardianSerializer,
)
from .permissions import IsAdmin

User = get_user_model()


class BeneficiaryViewSet(viewsets.ModelViewSet):
    queryset = Beneficiary.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "community_number": ["exact"],
        "gender": ["exact"],
        "sponsorship_status": ["exact"],
        "village": ["exact"],
    }
    search_fields = ["last_name", "child_number", "short_name", "village"]
    ordering_fields = [
        "community_number",
        "last_name",
        "child_number",
        "participant_case_number",
        "gender",
        "short_name",
        "birthdate",
        "sponsorship_status",
        "enrollment_date",
        "narrative_date",
        "photo_date",
        "age",
        "village",
        "created_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()

        documents_filter = self.request.query_params.get("documents")
        if documents_filter == "uploaded":
            queryset = queryset.annotate(doc_count=Count(
                "documents")).filter(doc_count__gt=0)
        elif documents_filter == "missing":
            queryset = queryset.annotate(
                doc_count=Count("documents")).filter(doc_count=0)

        status_param = self.request.query_params.get("status")
        if status_param and status_param != "All":
            queryset = queryset.filter(sponsorship_status=status_param)

        community = self.request.query_params.get("community_number")
        if community:
            queryset = queryset.filter(community_number=community)

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return BeneficiaryListSerializer
        return BeneficiaryDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def all(self, request):
        queryset = self.get_queryset()
        serializer = BeneficiaryListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response(
                {"error": "Expected a list of beneficiaries"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_count = 0
        skipped_count = 0
        failed_count = 0
        failed_items = []

        for item in data:
            child_number = item.get("childNumber") or item.get("child_number")
            if not child_number:
                skipped_count += 1
                continue

            if Beneficiary.objects.filter(child_number=child_number).exists():
                skipped_count += 1
                continue

            serializer = BeneficiaryDetailSerializer(
                data=item,
                context={"request": request},
            )
            if serializer.is_valid():
                serializer.save(created_by=request.user)
                created_count += 1
            else:
                failed_count += 1
                failed_items.append(
                    {"data": item, "errors": serializer.errors})

        return Response(
            {
                "created_count": created_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
                "failed": failed_items,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["delete"])
    def clear_all(self, request):
        if not request.user.role == "admin":
            return Response(
                {"error": "Only admins can clear all beneficiaries"},
                status=status.HTTP_403_FORBIDDEN,
            )
        count = Beneficiary.objects.count()
        Beneficiary.objects.all().delete()
        return Response(
            {"message": f"Deleted {count} beneficiaries"},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def import_guardians(self, request):
        confirm = request.query_params.get(
            "confirm", "false").lower() == "true"
        rows = request.data
        if not isinstance(rows, list):
            return Response(
                {"error": "Expected a list of guardian records"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        matched = 0
        unmatched = 0
        duplicates = 0
        invalid = 0
        preview_rows = []

        for row in rows:
            child_number = row.get("child_number", "").strip()
            guardian_name = row.get("name", "").strip()
            relationship = row.get("relationship", "").strip()

            if not child_number or not guardian_name or not relationship:
                invalid += 1
                preview_rows.append({**row, "status": "invalid"})
                continue

            beneficiary = Beneficiary.objects.filter(
                child_number=child_number).first()
            if not beneficiary:
                unmatched += 1
                preview_rows.append(
                    {**row, "status": "unmatched", "beneficiary_name": None})
                continue

            if Guardian.objects.filter(beneficiary=beneficiary, relationship=relationship).exists():
                duplicates += 1
                preview_rows.append({
                    **row,
                    "status": "duplicate",
                    "beneficiary_name": beneficiary.last_name,
                })
                continue

            matched += 1
            preview_rows.append({
                **row,
                "status": "matched",
                "beneficiary_name": beneficiary.last_name,
            })

            if confirm:
                Guardian.objects.create(
                    beneficiary=beneficiary,
                    name=guardian_name,
                    relationship=relationship,
                    phone=row.get("phone", ""),
                    email=row.get("email", ""),
                    address=row.get("address", ""),
                    notes=row.get("notes", ""),
                    id_number=row.get("id_number", ""),
                )

        return Response({
            "total_rows": len(rows),
            "matched": matched,
            "unmatched": unmatched,
            "duplicates": duplicates,
            "invalid": invalid,
            "rows": preview_rows,
        })

    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        beneficiary = self.get_object()
        text = request.data.get("text")
        if not text:
            return Response(
                {"error": "Text is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        note = Note.objects.create(
            beneficiary=beneficiary,
            author=request.user.email,
            text=text,
        )
        serializer = NoteSerializer(note)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def documents(self, request, pk=None):
        beneficiary = self.get_object()
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "File is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc = Document.objects.create(
            beneficiary=beneficiary,
            file=file_obj,
            name=file_obj.name,
            size=file_obj.size,
            type=file_obj.content_type or "",
        )
        serializer = DocumentSerializer(doc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="documents/(?P<doc_id>[^/.]+)")
    def delete_document(self, request, pk=None, doc_id=None):
        beneficiary = self.get_object()
        try:
            doc = beneficiary.documents.get(id=doc_id)
        except Document.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def guardians(self, request, pk=None):
        beneficiary = self.get_object()
        guardians = beneficiary.guardians.all()
        serializer = GuardianSerializer(guardians, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="guardians")
    def add_guardian(self, request, pk=None):
        beneficiary = self.get_object()
        serializer = GuardianSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(beneficiary=beneficiary)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmployeeActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == "admin":
            employees = User.objects.filter(role="employee", is_active=True)
            stats = []
            for emp in employees:
                count = SupportLog.objects.filter(logged_by=emp.email).values(
                    "beneficiary_id").distinct().count()
                stats.append({"email": emp.email, "beneficiary_count": count})
            return Response({"employee_stats": stats})
        else:
            count = SupportLog.objects.filter(logged_by=user.email).values(
                "beneficiary_id").distinct().count()
            return Response({"employee_stats": [{"email": user.email, "beneficiary_count": count}]})


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        is_admin = request.user.role == "admin"

        if is_admin:
            beneficiary_queryset = Beneficiary.objects.all()
            support_queryset = SupportLog.objects.select_related(
                "beneficiary").all()
        else:
            employee_email = request.user.email
            employee_logs = SupportLog.objects.filter(logged_by=employee_email)
            beneficiary_ids = employee_logs.values_list(
                "beneficiary_id", flat=True).distinct()
            beneficiary_queryset = Beneficiary.objects.filter(
                id__in=beneficiary_ids)
            support_queryset = employee_logs

        beneficiary_count = beneficiary_queryset.count()
        total_benefits = support_queryset.count()

        benefit_rows = support_queryset.values("type").annotate(
            count=Count("id")).order_by("-count", "type")
        benefit_types = []
        for row in benefit_rows:
            count = row["count"]
            percentage = round((count / total_benefits) *
                               100, 1) if total_benefits else 0
            benefit_types.append(
                {"type": row["type"] or "Other", "count": count, "percentage": percentage})

        if is_admin:
            employee_users = User.objects.filter(
                role="employee", is_active=True).order_by("email")
            employee_stats = []
            for emp in employee_users:
                count = SupportLog.objects.filter(logged_by=emp.email).values(
                    "beneficiary_id").distinct().count()
                employee_stats.append(
                    {"email": emp.email, "beneficiary_count": count})
            employee_count = employee_users.count()
        else:
            count = support_queryset.values(
                "beneficiary_id").distinct().count()
            employee_stats = [
                {"email": request.user.email, "beneficiary_count": count}]
            employee_count = 1

        return Response({
            "beneficiary_count": beneficiary_count,
            "employee_count": employee_count,
            "total_benefits": total_benefits,
            "benefit_types": benefit_types,
            "employee_stats": employee_stats,
        })
