from django.contrib import admin
from .models import User, OTP, UserPasswordHistory, ActivityLog, PublicKey, ChatMessage

admin.site.register(User)
admin.site.register(OTP)
admin.site.register(UserPasswordHistory)
admin.site.register(ActivityLog)
admin.site.register(PublicKey)
admin.site.register(ChatMessage)
