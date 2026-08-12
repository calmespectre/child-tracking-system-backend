from rest_framework.routers import DefaultRouter

from .views import SupportLogViewSet

router = DefaultRouter()

router.register(
    r"",
    SupportLogViewSet,
    basename="support-log",
)

urlpatterns = router.urls
