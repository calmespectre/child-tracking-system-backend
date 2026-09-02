from rest_framework import serializers
from .models import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(
        source="sender.email", read_only=True)
    sender_name = serializers.CharField(
        source="sender.username", read_only=True)
    recipient_email = serializers.EmailField(
        source="recipient.email", read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "sender", "sender_email", "sender_name", "recipient",
                  "recipient_email", "message", "attachment", "attachment_type", "timestamp", "is_read"]
        read_only_fields = ["id", "sender", "timestamp", "is_read"]
