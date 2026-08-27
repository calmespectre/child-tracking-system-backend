from django.contrib import admin
from .models import Disbursement


@admin.register(Disbursement)
class DisbursementAdmin(admin.ModelAdmin):
    list_display = ['program', 'beneficiary_name',
                    'amount', 'status', 'date', 'created_at']
    list_filter = ['program', 'status', 'date']
    search_fields = ['beneficiary_name', 'case_number',
                     'admission_number', 'school', 'location']
