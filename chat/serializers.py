from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ChatMessage, UserConversation

User = get_user_model()


class ChatUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    is_pinned = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "name",
            "profile_picture",
            "is_pinned",
        ]

    def get_name(self, obj):
        first_name = getattr(obj, "first_name", "") or ""
        last_name = getattr(obj, "last_name", "") or ""
        full_name = f"{first_name} {last_name}".strip()

        if full_name:
            return full_name

        for field in ["full_name", "name", "employee_name"]:
            value = getattr(obj, field, None)
            if value:
                return str(value).strip()

        return getattr(obj, "username", None) or obj.email

    def get_profile_picture(self, obj):
        picture = getattr(obj, "profile_picture", None)

        if not picture:
            return None

        try:
            return picture.url
        except (ValueError, AttributeError):
            return None

    def get_is_pinned(self, obj):
        request = self.context.get("request")

        if not request:
            return False

        user1, user2 = (
            (request.user, obj)
            if request.user.pk < obj.pk
            else (obj, request.user)
        )

        from .models import Conversation

        conversation = Conversation.objects.filter(
            user1=user1,
            user2=user2
        ).first()

        if not conversation:
            return False

        return UserConversation.objects.filter(
            user=request.user,
            conversation=conversation,
            pinned=True
        ).exists()


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(
        source="sender.email",
        read_only=True
    )

    sender_name = serializers.SerializerMethodField()

    sender_profile_picture = serializers.SerializerMethodField()

    recipient_email = serializers.EmailField(
        source="recipient.email",
        read_only=True
    )

    attachment = serializers.FileField(read_only=True)

    reply_to_id = serializers.IntegerField(
        source="reply_to.id",
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender",
            "sender_email",
            "sender_name",
            "sender_profile_picture",
            "recipient",
            "recipient_email",
            "message",
            "attachment",
            "attachment_type",
            "timestamp",
            "is_read",
            "reply_to",
            "reply_to_id",
        ]

        read_only_fields = [
            "id",
            "sender",
            "sender_email",
            "sender_name",
            "sender_profile_picture",
            "recipient_email",
            "timestamp",
            "is_read",
            "reply_to",
            "reply_to_id",
        ]

    def get_sender_name(self, obj):
        sender = obj.sender

        first_name = getattr(sender, "first_name", "") or ""
        last_name = getattr(sender, "last_name", "") or ""
        full_name = f"{first_name} {last_name}".strip()

        if full_name:
            return full_name

        for field in ["full_name", "name", "employee_name"]:
            value = getattr(sender, field, None)
            if value:
                return str(value).strip()

        return getattr(sender, "username", None) or sender.email

    def get_sender_profile_picture(self, obj):
        picture = getattr(obj.sender, "profile_picture", None)

        if not picture:
            return None

        try:
            return picture.url
        except (ValueError, AttributeError):
            return None


class UserConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserConversation
        fields = [
            "id",
            "pinned",
            "last_read_timestamp"
        ]