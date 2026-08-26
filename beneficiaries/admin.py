from django.contrib import admin
from .models import Beneficiary, Guardian, Document, Note

admin.site.register(Beneficiary)
admin.site.register(Guardian)
admin.site.register(Document)
admin.site.register(Note)
