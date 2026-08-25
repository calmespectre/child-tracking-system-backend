from rest_framework import serializers
from .models import Bursary


class BursarySerializer(serializers.ModelSerializer):
    beneficiary_id = serializers.SerializerMethodField()
    beneficiary_child_number = serializers.SerializerMethodField()

    class Meta:
        model = Bursary
        fields = [
            "id", "zone", "case_number", "admission_number",
            "beneficiary_name", "school", "grade", "performance",
            "account_number", "branch", "amount", "date",
            "status", "notes",
            "beneficiary_id", "beneficiary_child_number",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "beneficiary_id", "beneficiary_child_number",
            "created_by", "created_at", "updated_at",
        ]

    def get_beneficiary_id(self, obj):
        return obj.beneficiary.id if obj.beneficiary else None

    def get_beneficiary_child_number(self, obj):
        return obj.beneficiary.child_number if obj.beneficiary else None
