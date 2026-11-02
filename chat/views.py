from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status

from .models import ChatMessage, Conversation, UserConversation
from .serializers import ChatMessageSerializer, ChatUserSerializer

User = get_user_model()


class ChatUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.exclude(
            id=request.user.id
        )

        serializer = ChatUserSerializer(
            users,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data)


class ChatMessageListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_conversation(self, user1, user2):
        if user1.pk > user2.pk:
            user1, user2 = user2, user1

        conversation, created = Conversation.objects.get_or_create(
            user1=user1,
            user2=user2
        )

        return conversation

    def get(self, request):
        recipient_email = request.query_params.get(
            "recipient", ""
        ).strip()

        if not recipient_email:
            return Response(
                {"detail": "Recipient query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            recipient = User.objects.get(
                email__iexact=recipient_email
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Staff member not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if recipient.pk == request.user.pk:
            return Response(
                {"detail": "You cannot open a conversation with yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        self.get_conversation(request.user, recipient)

        messages = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=recipient) |
            Q(sender=recipient, recipient=request.user)
        ).select_related(
            "sender",
            "recipient",
            "reply_to",
            "reply_to__sender"
        ).order_by("timestamp", "id")

        serializer = ChatMessageSerializer(
            messages,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data)

    @transaction.atomic
    def post(self, request):
        recipient_email = request.data.get(
            "recipient", ""
        ).strip()

        message_text = request.data.get(
            "message", ""
        ).strip()

        attachment = request.FILES.get("attachment")
        reply_to_id = request.data.get("reply_to")

        if not recipient_email:
            return Response(
                {"detail": "Recipient is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not message_text and not attachment:
            return Response(
                {"detail": "A message or attachment is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if attachment and attachment.size > 25 * 1024 * 1024:
            return Response(
                {"detail": "The maximum attachment size is 25 MB."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            recipient = User.objects.get(
                email__iexact=recipient_email
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Recipient not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if recipient.pk == request.user.pk:
            return Response(
                {"detail": "You cannot send a message to yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        conversation = self.get_conversation(
            request.user,
            recipient
        )

        reply_to = None

        if reply_to_id:
            try:
                reply_to = ChatMessage.objects.get(
                    id=reply_to_id
                )
            except (ChatMessage.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"detail": "The message you are replying to could not be found."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            valid_reply = (
                (
                    reply_to.sender_id == request.user.pk and
                    reply_to.recipient_id == recipient.pk
                ) or (
                    reply_to.sender_id == recipient.pk and
                    reply_to.recipient_id == request.user.pk
                )
            )

            if not valid_reply:
                return Response(
                    {"detail": "You cannot reply to a message outside this conversation."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        chat_message = ChatMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            message=message_text,
            attachment=attachment,
            attachment_type=(
                attachment.content_type or "application/octet-stream"
                if attachment else ""
            ),
            reply_to=reply_to
        )

        conversation.save(update_fields=["updated_at"])

        serializer = ChatMessageSerializer(
            chat_message,
            context={"request": request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class ChatMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        recipient_email = request.data.get(
            "recipient", ""
        ).strip()

        if not recipient_email:
            return Response(
                {"detail": "Recipient is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            sender = User.objects.get(
                email__iexact=recipient_email
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Staff member not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        updated = ChatMessage.objects.filter(
            sender=sender,
            recipient=request.user,
            is_read=False
        ).update(is_read=True)

        return Response(
            {"marked_read": updated},
            status=status.HTTP_200_OK
        )


class ConversationPinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        other_email = request.data.get(
            "other_email", ""
        ).strip()

        if not other_email:
            return Response(
                {"detail": "Other email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            other = User.objects.get(
                email__iexact=other_email
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Staff member not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if other.pk == request.user.pk:
            return Response(
                {"detail": "You cannot pin a conversation with yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user1, user2 = (
            (request.user, other)
            if request.user.pk < other.pk
            else (other, request.user)
        )

        conversation, created = Conversation.objects.get_or_create(
            user1=user1,
            user2=user2
        )

        user_conversation, created = UserConversation.objects.get_or_create(
            user=request.user,
            conversation=conversation
        )

        user_conversation.pinned = not user_conversation.pinned
        user_conversation.save(update_fields=["pinned"])

        return Response(
            {"pinned": user_conversation.pinned},
            status=status.HTTP_200_OK
        )