from django.urls import path
from .views import DisbursementViewSet

disbursement_list = DisbursementViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
disbursement_detail = DisbursementViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})
disbursement_import = DisbursementViewSet.as_view({
    'post': 'import_bursaries'
})

urlpatterns = [
    path('disbursements/<str:program>/',
         disbursement_list, name='disbursement-list'),
    path('disbursements/<str:program>/<int:pk>/',
         disbursement_detail, name='disbursement-detail'),
    path('disbursements/<str:program>/import/',
         disbursement_import, name='disbursement-import'),
]
