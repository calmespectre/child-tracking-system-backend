from django.urls import path
from .views import (ChatUserListView, ChatMessageListView, ChatMarkReadView,
                    ConversationPinView)

urlpatterns = [
    path("chat/users/", ChatUserListView.as_view(), name="chat-users"),
    path("chat/messages/", ChatMessageListView.as_view(), name="chat-messages"),
    path("chat/messages/mark-read/",
         ChatMarkReadView.as_view(), name="chat-mark-read"),
    path("chat/conversation/pin/", ConversationPinView.as_view(), name="chat-pin"),
]
