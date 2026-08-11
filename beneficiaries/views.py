from django.contrib.auth import get_user_model
from django.db.models import Count

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Beneficiary, SupportLog
from .serializers import (
    BeneficiaryListSerializer,
    BeneficiaryDetailSerializer,
)


User = get_user_model()


class BeneficiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    queryset = Beneficiary.objects.all().order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return BeneficiaryListSerializer

        return BeneficiaryDetailSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = (
            Beneficiary.objects
            .select_related("created_by")
            .prefetch_related(
                "notes",
                "documents",
                "support_logs",
            )
            .order_by("-created_at")
        )

        # Admins can see everything.
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return queryset

        # Employees only see beneficiaries they created.
        return queryset.filter(created_by=user)


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
                logged_by=user
            )

        beneficiary_count = beneficiaries.count()
        total_benefits = support_logs.count()

        # ---------------------------------------------------------
        # BENEFIT TYPES
        # ---------------------------------------------------------

        benefit_queryset = (
            support_logs
            .values("type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        benefit_types = []

        for item in benefit_queryset:
            count = item["count"]

            percentage = (
                round((count / total_benefits) * 100, 1)
                if total_benefits > 0
                else 0
            )

            benefit_types.append(
                {
                    "type": item["type"] or "Unknown",
                    "count": count,
                    "percentage": percentage,
                }
            )

        # ---------------------------------------------------------
        # EMPLOYEE STATS
        # ---------------------------------------------------------

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
                    "beneficiary_count": beneficiary_count,
                }
            )

        # ---------------------------------------------------------
        # RESPONSE
        # ---------------------------------------------------------

        return Response(
            {
                "beneficiary_count": beneficiary_count,
                "employee_count": (
                    User.objects.filter(
                        is_active=True
                    ).count()
                    if is_admin
                    else 1
                ),
                "total_benefits": total_benefits,
                "benefit_types": benefit_types,
                "employee_stats": employee_stats,
            },
            status=status.HTTP_200_OK,
        )


class EmployeeActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        email = request.query_params.get("email")

        is_admin = (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "role", "").lower() == "admin"
        )

        # ---------------------------------------------------------
        # ADMIN
        # ---------------------------------------------------------

        if is_admin:
            if email:
                employee = User.objects.filter(
                    email__iexact=email
                ).first()

                if not employee:
                    return Response(
                        {
                            "detail": "Employee not found."
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

                beneficiary_count = Beneficiary.objects.filter(
                    created_by=employee
                ).count()

                benefit_count = SupportLog.objects.filter(
                    logged_by=employee
                ).count()

                return Response(
                    {
                        "email": employee.email,
                        "beneficiary_count": beneficiary_count,
                        "benefit_count": benefit_count,
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
                        "beneficiary_count": Beneficiary.objects.filter(
                            created_by=employee
                        ).count(),
                        "benefit_count": SupportLog.objects.filter(
                            logged_by=employee
                        ).count(),
                    }
                )

            return Response(results)

        # ---------------------------------------------------------
        # EMPLOYEE
        # ---------------------------------------------------------

        beneficiary_count = Beneficiary.objects.filter(
            created_by=user
        ).count()

        benefit_count = SupportLog.objects.filter(
            logged_by=user
        ).count()

        return Response(
            {
                "email": user.email,
                "beneficiary_count": beneficiary_count,
                "benefit_count": benefit_count,
            }
        )
