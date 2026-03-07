from django.db import models
from decimal import Decimal
import uuid as _uuid


class Guest(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class Room(models.Model):
    ROOM_TYPES = [
        ('standard', 'Standard'),
        ('deluxe', 'Deluxe'),
        ('suite', 'Suite'),
    ]
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Maintenance'),
    ]

    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')

    def __str__(self):
        return f'Room {self.room_number} ({self.room_type})'


class SiteSetting(models.Model):
    festive_mode = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Site Setting'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Booking(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='bookings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    check_in = models.DateField()
    check_out = models.DateField()
    discount_percent = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    group_ref = models.UUIDField(default=_uuid.uuid4, db_index=True)

    def __str__(self):
        return f'{self.guest.name} - Room {self.room.room_number} ({self.check_in} to {self.check_out})'

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    @property
    def base_price(self):
        return self.room.price_per_night * self.nights

    @property
    def discount_amount(self):
        return (self.base_price * self.discount_percent / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def final_price(self):
        return self.base_price - self.discount_amount
