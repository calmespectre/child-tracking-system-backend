from django.contrib import admin
from .models import User, OTP, UserPasswordHistory, ActivityLog

admin.site.register(User)
admin.site.register(OTP)
admin.site.register(UserPasswordHistory)
admin.site.register(ActivityLog)
