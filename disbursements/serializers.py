from rest_framework import serializers
from .models import Bursary


class BursarySerializer(serializers.ModelSerializer):
    beneficiary_id = serializers.IntegerField(
        source="beneficiary.id",
        read_only=True
    )
    beneficiary_child_number = serializers.CharField(
        source="beneficiary.child_number",
        read_only=True
    )

    class Meta:
        model = Bursary
        fields = [
            "id",
            "zone",
            "case_number",
            "admission_number",
            "beneficiary_name",
            "school",
            "grade",
            "performance",
            "account_number",
            "branch",
            "amount",
            "date",
            "status",
            "notes",
            "beneficiary_id",
            "beneficiary_child_number",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "beneficiary_id",
            "beneficiary_child_number",
            "created_by",
            "created_at",
            "updated_at",
        ]