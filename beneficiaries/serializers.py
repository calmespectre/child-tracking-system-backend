from rest_framework import serializers
from .models import Beneficiary, Guardian, Document, Note


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = ['id', 'name', 'relationship', 'phone',
                  'email', 'address', 'id_number', 'notes']


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'name', 'file', 'type', 'size', 'uploaded_at']


class NoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.email', read_only=True)

    class Meta:
        model = Note
        fields = ['id', 'author', 'author_name', 'text', 'date']


class BeneficiarySerializer(serializers.ModelSerializer):
    guardians = GuardianSerializer(many=True, read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    notes = NoteSerializer(many=True, read_only=True)
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Beneficiary
        fields = [
            'id', 'community_number', 'last_name', 'child_number',
            'participant_case_number', 'gender', 'short_name', 'birthdate',
            'sponsorship_status', 'enrollment_date', 'narrative_date', 'photo_date',
            'age', 'village', 'created_at', 'updated_at', 'guardians', 'documents',
            'notes', 'document_count'
        ]

    def get_document_count(self, obj):
        return obj.documents.count()


class BeneficiaryListSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()
    has_documents = serializers.BooleanField(source='documents.exists')

    class Meta:
        model = Beneficiary
        fields = [
            'id', 'community_number', 'last_name', 'child_number',
            'participant_case_number', 'gender', 'short_name', 'birthdate',
            'sponsorship_status', 'enrollment_date', 'narrative_date', 'photo_date',
            'age', 'village', 'document_count', 'has_documents'
        ]

    def get_document_count(self, obj):
        return obj.documents.count()
