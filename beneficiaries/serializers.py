from rest_framework import serializers

from .models import (
    Beneficiary,
    Note,
    Document,
    SupportLog,
)


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = [
            "id",
            "author",
            "date",
            "text",
        ]


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "file",
            "name",
            "size",
            "type",
            "uploaded_at",
        ]


class SupportLogSerializer(serializers.ModelSerializer):
    beneficiaryName = serializers.SerializerMethodField()
    beneficiaryId = serializers.CharField(
        source="beneficiary.child_number",
        read_only=True,
    )

    class Meta:
        model = SupportLog
        fields = [
            "id",
            "beneficiary",
            "beneficiaryName",
            "beneficiaryId",
            "type",
            "amount",
            "date",
            "notes",
            "status",
            "approved_by",
            "status_updated_at",
            "logged_at",
            "logged_by",
        ]
        read_only_fields = [
            "id",
            "beneficiary",
            "beneficiaryName",
            "beneficiaryId",
            "logged_at",
        ]

    def get_beneficiaryName(self, obj):
        return obj.beneficiary.short_name or obj.beneficiary.last_name


class BeneficiaryListSerializer(serializers.ModelSerializer):
    communityNumber = serializers.CharField(
        source="community_number",
        read_only=True,
    )

    lastName = serializers.CharField(
        source="last_name",
        read_only=True,
    )

    childNumber = serializers.CharField(
        source="child_number",
        read_only=True,
    )

    participantCaseNumber = serializers.CharField(
        source="participant_case_number",
        read_only=True,
    )

    shortName = serializers.CharField(
        source="short_name",
        read_only=True,
    )

    sponsorshipStatus = serializers.CharField(
        source="sponsorship_status",
        read_only=True,
    )

    enrollmentDate = serializers.DateField(
        source="enrollment_date",
        read_only=True,
    )

    narrativeDate = serializers.DateField(
        source="narrative_date",
        read_only=True,
    )

    photoDate = serializers.DateField(
        source="photo_date",
        read_only=True,
    )

    createdAt = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )

    updatedAt = serializers.DateTimeField(
        source="updated_at",
        read_only=True,
    )

    createdBy = serializers.PrimaryKeyRelatedField(
        source="created_by",
        read_only=True,
    )

    class Meta:
        model = Beneficiary

        fields = [
            "id",
            "communityNumber",
            "lastName",
            "childNumber",
            "participantCaseNumber",
            "gender",
            "shortName",
            "birthdate",
            "sponsorshipStatus",
            "enrollmentDate",
            "narrativeDate",
            "photoDate",
            "age",
            "village",
            "createdAt",
            "updatedAt",
            "createdBy",
        ]


class BeneficiaryDetailSerializer(serializers.ModelSerializer):
    notes = NoteSerializer(
        many=True,
        read_only=True,
    )

    documents = DocumentSerializer(
        many=True,
        read_only=True,
    )

    supportLog = SupportLogSerializer(
        source="support_logs",
        many=True,
        read_only=True,
    )

    communityNumber = serializers.CharField(
        source="community_number",
        required=False,
        allow_blank=True,
        default="",
    )

    lastName = serializers.CharField(
        source="last_name",
    )

    childNumber = serializers.CharField(
        source="child_number",
    )

    participantCaseNumber = serializers.CharField(
        source="participant_case_number",
        required=False,
        allow_blank=True,
        default="",
    )

    shortName = serializers.CharField(
        source="short_name",
        required=False,
        allow_blank=True,
        default="",
    )

    sponsorshipStatus = serializers.CharField(
        source="sponsorship_status",
        required=False,
        default="Sponsored",
    )

    enrollmentDate = serializers.DateField(
        source="enrollment_date",
        required=False,
        allow_null=True,
    )

    narrativeDate = serializers.DateField(
        source="narrative_date",
        required=False,
        allow_null=True,
    )

    photoDate = serializers.DateField(
        source="photo_date",
        required=False,
        allow_null=True,
    )

    createdAt = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )

    updatedAt = serializers.DateTimeField(
        source="updated_at",
        read_only=True,
    )

    createdBy = serializers.PrimaryKeyRelatedField(
        source="created_by",
        read_only=True,
    )

    class Meta:
        model = Beneficiary

        fields = [
            "id",
            "communityNumber",
            "lastName",
            "childNumber",
            "participantCaseNumber",
            "gender",
            "shortName",
            "birthdate",
            "sponsorshipStatus",
            "enrollmentDate",
            "narrativeDate",
            "photoDate",
            "age",
            "village",
            "createdAt",
            "updatedAt",
            "createdBy",
            "notes",
            "documents",
            "supportLog",
        ]

    def create(self, validated_data):
        request = self.context.get("request")

        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user

        return Beneficiary.objects.create(
            **validated_data
        )

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        return instance
