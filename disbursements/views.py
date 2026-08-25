from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import PageNumberPagination

from .models import Bursary
from .serializers import BursarySerializer


class BursaryPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class BursaryViewSet(ModelViewSet):
    serializer_class = BursarySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = BursaryPagination
    filter_backends = [OrderingFilter]

    def get_queryset(self):
        queryset = Bursary.objects.all()   # no select_related needed

        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(beneficiary_name__icontains=search) |
                Q(case_number__icontains=search) |
                Q(admission_number__icontains=search) |
                Q(school__icontains=search)
            )
        return queryset
