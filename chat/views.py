from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import ChatMessage, Conversation, UserConversation
from .serializers import ChatMessageSerializer, UserConversationSerializer

User = get_user_model()


class ChatUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.exclude(id=request.user.id).only(
            'id', 'email', 'username', 'profile_picture', 'public_key')
        from accounts.serializers import UserProfileSerializer
        serializer = UserProfileSerializer(users, many=True)
        return Response(serializer.data)


class ChatMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_conversation(self, user1, user2):
        if user1.id > user2.id:
            user1, user2 = user2, user1
        conv, _ = Conversation.objects.get_or_create(user1=user1, user2=user2)
        return conv

    def get(self, request):
        recipient_email = request.query_params.get('recipient', '').strip()
        if not recipient_email:
            return Response({'detail': 'recipient query parameter required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            recipient = User.objects.get(email__iexact=recipient_email)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        messages = ChatMessage.objects.filter(
            sender=request.user, recipient=recipient
        ) | ChatMessage.objects.filter(
            sender=recipient, recipient=request.user
        )
        messages = messages.order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request):
        recipient_email = request.data.get('recipient', '').strip()
        message_text = request.data.get('message', '').strip()
        attachment = request.FILES.get('attachment')
        reply_to_id = request.data.get('reply_to')
        encrypted_key = request.data.get('encrypted_symmetric_key', '')

        if not recipient_email:
            return Response({'detail': 'recipient is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not message_text and not attachment:
            return Response({'detail': 'message or attachment is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            recipient = User.objects.get(email__iexact=recipient_email)
        except User.DoesNotExist:
            return Response({'detail': 'Recipient not found.'}, status=status.HTTP_404_NOT_FOUND)
        if recipient == request.user:
            return Response({'detail': 'Cannot send message to yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        chat_message = ChatMessage(
            sender=request.user,
            recipient=recipient,
            message=message_text,
            encrypted_symmetric_key=encrypted_key
        )
        if reply_to_id:
            try:
                reply_to = ChatMessage.objects.get(
                    id=reply_to_id, sender=recipient)
                chat_message.reply_to = reply_to
            except ChatMessage.DoesNotExist:
                pass
        if attachment:
            chat_message.attachment = attachment
            chat_message.attachment_type = attachment.content_type or 'application/octet-stream'
        chat_message.save()
        serializer = ChatMessageSerializer(chat_message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChatMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        recipient_email = request.data.get('recipient', '').strip()
        if not recipient_email:
            return Response({'detail': 'recipient is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            sender = User.objects.get(email__iexact=recipient_email)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        updated = ChatMessage.objects.filter(
            sender=sender, recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({'marked_read': updated}, status=status.HTTP_200_OK)


class ConversationPinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        other_email = request.data.get('other_email')
        if not other_email:
            return Response({'detail': 'other_email required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            other = User.objects.get(email__iexact=other_email)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        user1, user2 = (request.user, other) if request.user.id < other.id else (
            other, request.user)
        conv, _ = Conversation.objects.get_or_create(user1=user1, user2=user2)
        uc, created = UserConversation.objects.get_or_create(
            user=request.user, conversation=conv)
        uc.pinned = not uc.pinned
        uc.save()
        return Response({'pinned': uc.pinned}, status=status.HTTP_200_OK)
