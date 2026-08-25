from rest_framework.routers import DefaultRouter
from .views import BursaryViewSet

router = DefaultRouter()
router.register(r"bursaries", BursaryViewSet, basename="bursary")
urlpatterns = router.urls
