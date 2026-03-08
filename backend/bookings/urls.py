from rest_framework.routers import DefaultRouter
from .views import GuestViewSet, RoomViewSet, BookingViewSet

router = DefaultRouter()
router.register('guests', GuestViewSet)
router.register('rooms', RoomViewSet)
router.register('bookings', BookingViewSet)

urlpatterns = router.urls
