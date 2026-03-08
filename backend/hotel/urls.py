from django.contrib import admin
from django.urls import path, include
from bookings import views as v

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('bookings.urls')),
    path('api/stats/', v.api_stats, name='api_stats'),
    path('api/festive/', v.toggle_festive, name='toggle_festive'),
    path('api/next-room-number/', v.next_room_number, name='next_room_number'),
    path('api/room-numbers/', v.available_room_numbers, name='available_room_numbers'),
    path('api/maintenance/<int:room_id>/', v.toggle_maintenance, name='toggle_maintenance'),
    path('login/', v.staff_login, name='staff_login'),
    path('logout/', v.staff_logout, name='staff_logout'),
    path('', v.dashboard, name='dashboard'),
    path('rooms/', v.rooms_page, name='rooms'),
    path('guests/', v.guests_page, name='guests'),
    path('bookings/', v.bookings_page, name='bookings_page'),
    # ── Guest-facing hotel website ──
    path('hotel/', v.user_home, name='user_home'),
    path('hotel/rooms/', v.user_rooms, name='user_rooms'),
    path('hotel/book/', v.user_book, name='user_book'),
    path('hotel/confirm/<int:booking_id>/', v.user_confirm, name='user_confirm'),
    path('hotel/my-bookings/', v.my_bookings, name='my_bookings'),
    path('hotel/modify/<int:booking_id>/', v.modify_booking, name='modify_booking'),
]
