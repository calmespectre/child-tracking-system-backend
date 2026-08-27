from rest_framework import serializers
from .models import Disbursement


class DisbursementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disbursement
        fields = [
            "id", "program", "zone", "case_number", "admission_number",
            "beneficiary_name", "school", "grade", "performance",
            "account_number", "branch", "location", "description",
            "quantity", "amount", "date", "status", "notes",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]
