from django.core.management.base import BaseCommand
from bookings.models import Room
from decimal import Decimal

ROOM_CONFIGS = {
    'standard': {'range': range(101, 200), 'price': Decimal('2000')},
    'deluxe':   {'range': range(201, 300), 'price': Decimal('4000')},
    'suite':    {'range': range(301, 351), 'price': Decimal('8000')},
}


class Command(BaseCommand):
    help = 'Pre-populate all rooms for each type (skips existing)'

    def handle(self, *args, **kwargs):
        created = 0
        for rtype, config in ROOM_CONFIGS.items():
            for n in config['range']:
                _, was_created = Room.objects.get_or_create(
                    room_number=str(n),
                    defaults={
                        'room_type': rtype,
                        'price_per_night': config['price'],
                        'status': 'available',
                    },
                )
                if was_created:
                    created += 1
        self.stdout.write(self.style.SUCCESS(
            f'Done — {created} rooms created.'
        ))
