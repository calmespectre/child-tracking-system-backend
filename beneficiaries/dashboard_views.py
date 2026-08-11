from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Beneficiary, SupportLog

User = get_user_model()


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        is_admin = getattr(request.user, "role", "") == "admin"

        if is_admin:
            beneficiary_queryset = Beneficiary.objects.all()
            support_queryset = SupportLog.objects.select_related(
                "beneficiary"
            ).all()
        else:
            employee_email = request.user.email

            employee_logs = SupportLog.objects.filter(
                logged_by=employee_email
            )

            beneficiary_ids = employee_logs.values_list(
                "beneficiary_id",
                flat=True,
            ).distinct()

            beneficiary_queryset = Beneficiary.objects.filter(
                id__in=beneficiary_ids
            )

            support_queryset = employee_logs

        beneficiary_count = beneficiary_queryset.count()
        total_benefits = support_queryset.count()

        benefit_rows = (
            support_queryset
            .values("type")
            .annotate(count=Count("id"))
            .order_by("-count", "type")
        )

        benefit_types = []

        for row in benefit_rows:
            count = row["count"]

            percentage = (
                round((count / total_benefits) * 100, 1)
                if total_benefits
                else 0
            )

            benefit_types.append(
                {
                    "type": row["type"] or "Other",
                    "count": count,
                    "percentage": percentage,
                }
            )

        if is_admin:
            employee_users = User.objects.filter(
                role="employee",
                is_active=True,
            ).order_by("email")

            employee_stats = []

            for employee in employee_users:
                count = (
                    SupportLog.objects
                    .filter(logged_by=employee.email)
                    .values("beneficiary_id")
                    .distinct()
                    .count()
                )

                employee_stats.append(
                    {
                        "email": employee.email,
                        "beneficiary_count": count,
                    }
                )

            employee_count = employee_users.count()

        else:
            count = (
                support_queryset
                .values("beneficiary_id")
                .distinct()
                .count()
            )

            employee_stats = [
                {
                    "email": request.user.email,
                    "beneficiary_count": count,
                }
            ]

            employee_count = 1

        return Response(
            {
                "beneficiary_count": beneficiary_count,
                "employee_count": employee_count,
                "total_benefits": total_benefits,
                "benefit_types": benefit_types,
                "employee_stats": employee_stats,
            }
        )
