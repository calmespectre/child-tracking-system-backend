from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import ChatMessage
from .serializers import ChatMessageSerializer

User = get_user_model()


class ChatUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.exclude(id=request.user.id).only(
            'id', 'email', 'username', 'profile_picture')
        from accounts.serializers import UserProfileSerializer
        serializer = UserProfileSerializer(users, many=True)
        return Response(serializer.data)


class ChatMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        recipient_email = request.query_params.get('recipient', '').strip()
        if not recipient_email:
            return Response(
                {'detail': 'recipient query parameter required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            recipient = User.objects.get(email__iexact=recipient_email)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        messages = ChatMessage.objects.filter(
            sender=request.user,
            recipient=recipient
        ) | ChatMessage.objects.filter(
            sender=recipient,
            recipient=request.user
        )
        messages = messages.order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request):
        recipient_email = request.data.get('recipient', '').strip()
        message_text = request.data.get('message', '').strip()
        attachment = request.FILES.get('attachment')
        if not recipient_email:
            return Response(
                {'detail': 'recipient is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not message_text and not attachment:
            return Response(
                {'detail': 'message or attachment is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            recipient = User.objects.get(email__iexact=recipient_email)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Recipient not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if recipient == request.user:
            return Response(
                {'detail': 'Cannot send message to yourself.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        chat_message = ChatMessage(
            sender=request.user,
            recipient=recipient,
            message=message_text
        )
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
            return Response(
                {'detail': 'recipient is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            sender = User.objects.get(email__iexact=recipient_email)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        updated = ChatMessage.objects.filter(
            sender=sender,
            recipient=request.user,
            is_read=False
        ).update(is_read=True)
        return Response({'marked_read': updated}, status=status.HTTP_200_OK)
