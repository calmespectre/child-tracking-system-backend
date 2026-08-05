from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count
from .models import Beneficiary, Note, Document, SupportLog
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
        if self.action == "list":
            return BeneficiaryListSerializer
        return BeneficiaryDetailSerializer

    def get_queryset(self):
        queryset = Beneficiary.objects.all()
        user = self.request.user

        if user.role == "employee":
            queryset = queryset.filter(created_by=user)

        search = self.request.query_params.get("search", "").strip()
        status_val = self.request.query_params.get("status")
        ordering = self.request.query_params.get("ordering", "-child_number")

        if search:
            queryset = queryset.filter(
                Q(last_name__icontains=search) |
                Q(child_number__icontains=search) |
                Q(village__icontains=search) |
                Q(community_number__icontains=search) |
                Q(short_name__icontains=search)
            )

        if status_val and status_val != "All":
            queryset = queryset.filter(sponsorship_status=status_val)

        if ordering in ["child_number", "-child_number"]:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by("-child_number")

        return queryset

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_create(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response({"error": "Expected a list of objects."}, status=status.HTTP_400_BAD_REQUEST)

        seen = set()
        unique_data = []
        for item in data:
            cn = item.get("childNumber")
            if cn and cn not in seen:
                seen.add(cn)
                unique_data.append(item)

        incoming_numbers = [item.get("childNumber")
                            for item in unique_data if item.get("childNumber")]
        existing = set(
            Beneficiary.objects.filter(child_number__in=incoming_numbers)
            .values_list("child_number", flat=True)
        )
        to_create = [item for item in unique_data if item.get(
            "childNumber") not in existing]
        skipped = len(data) - len(to_create)

        if not to_create:
            return Response({"created": [], "skipped": skipped}, status=status.HTTP_201_CREATED)

        serializer = BeneficiaryDetailSerializer(
            data=to_create, many=True,
            context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"created": serializer.data, "skipped": skipped}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="all")
    def all_beneficiaries(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = BeneficiaryListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="notes")
    def add_note(self, request, pk=None):
        beneficiary = self.get_object()
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(beneficiary=beneficiary)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="documents")
    def upload_document(self, request, pk=None):
        beneficiary = self.get_object()
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        doc = Document.objects.create(
            beneficiary=beneficiary,
            file=file,
            name=file.name,
            size=file.size,
            type=file.content_type or "",
        )
        serializer = DocumentSerializer(doc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="documents/(?P<doc_id>[^/.]+)")
    def delete_document(self, request, pk=None, doc_id=None):
        beneficiary = self.get_object()
        try:
            doc = beneficiary.documents.get(id=doc_id)
        except Document.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="support")
    def log_support(self, request, pk=None):
        beneficiary = self.get_object()
        serializer = SupportLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(beneficiary=beneficiary)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["delete"], url_path="clear_all", permission_classes=[IsAuthenticated, IsAdmin])
    def clear_all(self, request):
        Beneficiary.objects.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        user = self.request.user
        qs = Beneficiary.objects.all()
        if user.role == "employee":
            qs = qs.filter(created_by=user)

        beneficiary_count = qs.count()

        logs = SupportLog.objects.filter(beneficiary__in=qs)
        pending_disbursements = logs.filter(status="Pending").count()
        total_support = logs.aggregate(total=Sum("amount"))["total"] or 0

        return Response({
            "beneficiary_count": beneficiary_count,
            "pending_disbursements": pending_disbursements,
            "total_support": total_support,
        })
