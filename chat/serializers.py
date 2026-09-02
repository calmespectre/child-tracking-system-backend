from rest_framework import serializers
from .models import ChatMessage, UserConversation
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(
        source="sender.email",
        read_only=True
    )
    sender_name = serializers.CharField(
        source="sender.username",
        read_only=True
    )
    sender_public_key = serializers.SerializerMethodField()
    recipient_email = serializers.EmailField(
        source="recipient.email",
        read_only=True
    )
    reply_to_id = serializers.PrimaryKeyRelatedField(
        source="reply_to",
        read_only=True
    )

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender",
            "sender_email",
            "sender_name",
            "sender_public_key",
            "recipient",
            "recipient_email",
            "message",
            "attachment",
            "attachment_type",
            "timestamp",
            "is_read",
            "reply_to",
            "reply_to_id",
            "encrypted_symmetric_key"
        ]
        read_only_fields = [
            "id",
            "sender",
            "timestamp",
            "is_read",
            "sender_public_key",
            "reply_to_id"
        ]

    def get_sender_public_key(self, obj):
        try:
            return obj.sender.public_key.key
        except Exception:
            return None


class UserConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserConversation
        fields = [
            "id",
            "pinned",
            "last_read_timestamp"
        ]
