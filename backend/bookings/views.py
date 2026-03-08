from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from rest_framework import viewsets
from decimal import Decimal
import random
import uuid
from .models import Guest, Room, Booking, SiteSetting
from .serializers import GuestSerializer, RoomSerializer, BookingSerializer, BookingDetailSerializer


# ── Email helpers ───────────────────────────────────────────────────────────────

HOTEL_NAME = 'Grand Hotel'


def _send_booking_confirmation(primary_booking, all_bookings=None):
    if all_bookings is None:
        all_bookings = [primary_booking]
    try:
        rooms_summary = ', '.join(b.room.room_type.capitalize() for b in all_bookings)
        subject = f'Booking Confirmed — {HOTEL_NAME} | {len(all_bookings)} Room{"s" if len(all_bookings)>1 else ""}'
        html = render_to_string('email/booking_confirmation.html', {
            'booking': primary_booking,
            'all_bookings': all_bookings,
            'hotel_name': HOTEL_NAME,
            'hotel_email': settings.HOTEL_EMAIL,
        })
        msg = EmailMultiAlternatives(
            subject=subject,
            body=(
                f'Dear {primary_booking.guest.name},\n\n'
                f'Your booking is confirmed — {len(all_bookings)} room(s): {rooms_summary}\n'
                f'Check-in: {primary_booking.check_in}  Check-out: {primary_booking.check_out}\n'
                f'Please arrive with a valid ID. Thank you for choosing {HOTEL_NAME}!'
            ),
            from_email=f'{HOTEL_NAME} <{settings.HOTEL_EMAIL}>',
            to=[primary_booking.guest.email],
        )
        msg.attach_alternative(html, 'text/html')
        msg.send()
    except Exception as e:
        print(f'[Email] Confirmation failed: {e}')


def _send_modification_confirmation(booking):
    try:
        subject = f'Booking Modified — {HOTEL_NAME} | Booking #{booking.id}'
        html = render_to_string('email/booking_modified.html', {
            'booking': booking,
            'hotel_name': HOTEL_NAME,
            'hotel_email': settings.HOTEL_EMAIL,
        })
        msg = EmailMultiAlternatives(
            subject=subject,
            body=(
                f'Dear {booking.guest.name},\n\n'
                f'Your booking #{booking.id} has been updated.\n'
                f'Check-in: {booking.check_in}  Check-out: {booking.check_out}\n'
                f'Room: {booking.room.room_type.capitalize()}\n'
                f'Thank you for choosing {HOTEL_NAME}!'
            ),
            from_email=f'{HOTEL_NAME} <{settings.HOTEL_EMAIL}>',
            to=[booking.guest.email],
        )
        msg.attach_alternative(html, 'text/html')
        msg.send()
    except Exception as e:
        print(f'[Email] Modification confirmation failed: {e}')


def _send_admin_modification_notification(booking, changes):
    try:
        subject = f'Booking #{booking.id} Modified by Guest — {HOTEL_NAME}'
        html = render_to_string('email/admin_booking_modified.html', {
            'booking': booking,
            'changes': changes,
            'hotel_name': HOTEL_NAME,
        })
        msg = EmailMultiAlternatives(
            subject=subject,
            body=(
                f'Booking #{booking.id} was modified by {booking.guest.name} ({booking.guest.email}).\n'
                f'Changes: {", ".join(changes)}\n'
                f'New dates: {booking.check_in} to {booking.check_out}\n'
                f'Room type: {booking.room.room_type}'
            ),
            from_email=f'{HOTEL_NAME} <{settings.HOTEL_EMAIL}>',
            to=[settings.HOTEL_EMAIL],
        )
        msg.attach_alternative(html, 'text/html')
        msg.send()
    except Exception as e:
        print(f'[Email] Admin modification notification failed: {e}')


def _send_reassignment_email(booking, old_number, new_number):
    try:
        subject = f'Room Update — Booking #{booking.id} | {HOTEL_NAME}'
        html = render_to_string('email/room_reassigned.html', {
            'booking': booking, 'old_number': old_number, 'new_number': new_number,
            'hotel_name': HOTEL_NAME, 'hotel_email': settings.HOTEL_EMAIL,
        })
        msg = EmailMultiAlternatives(
            subject=subject,
            body=(
                f'Dear {booking.guest.name},\n\n'
                f'Your room for booking #{booking.id} has been reassigned.\n'
                f'Previous: Room {old_number}  →  New: Room {new_number}\n'
                f'All other details remain unchanged.\n\n'
                f'We apologise for any inconvenience. — {HOTEL_NAME}'
            ),
            from_email=f'{HOTEL_NAME} <{settings.HOTEL_EMAIL}>',
            to=[booking.guest.email],
        )
        msg.attach_alternative(html, 'text/html')
        msg.send()
    except Exception as e:
        print(f'[Email] Reassignment failed: {e}')


# ── REST API ViewSets ──────────────────────────────────────────────────────────

class GuestViewSet(viewsets.ModelViewSet):
    queryset = Guest.objects.all()
    serializer_class = GuestSerializer


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related('guest', 'room').all()

    def get_serializer_class(self):
        if self.action in ('retrieve', 'list'):
            return BookingDetailSerializer
        return BookingSerializer


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_stats():
    today = timezone.now().date()
    return {
        'total_rooms': Room.objects.count(),
        'available_rooms': Room.objects.filter(status='available').count(),
        'occupied_rooms': Room.objects.filter(status='occupied').count(),
        'maintenance_rooms': Room.objects.filter(status='maintenance').count(),
        'total_guests': Guest.objects.count(),
        'total_bookings': Booking.objects.count(),
        'today_checkins': Booking.objects.filter(check_in=today).count(),
        'today_checkouts': Booking.objects.filter(check_out=today).count(),
    }


def _category_data(festive):
    """Availability + pricing per room type for guest-facing pages."""
    cats = []
    for rtype, label in Room.ROOM_TYPES:
        rooms = Room.objects.filter(status='available', room_type=rtype)
        count = rooms.count()
        first = rooms.order_by('price_per_night').first()
        orig_price = first.price_per_night if first else None
        if festive and orig_price:
            display_price = (orig_price * Decimal('0.85')).quantize(Decimal('1'))
        else:
            display_price = orig_price
        cats.append({
            'type': rtype,
            'label': label,
            'count': count,
            'price': display_price,
            'orig_price': orig_price if festive else None,
        })
    return cats


# ── Auth ───────────────────────────────────────────────────────────────────────

def staff_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = None
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password'),
        )
        if user:
            auth_login(request, user)
            return redirect(request.GET.get('next', 'dashboard'))
        error = 'Invalid username or password.'
    return render(request, 'login.html', {'error': error})


def staff_logout(request):
    auth_logout(request)
    return redirect('user_home')


# ── Template Views ─────────────────────────────────────────────────────────────

@login_required(login_url='/login/')
def dashboard(request):
    recent_bookings = Booking.objects.select_related('guest', 'room').order_by('-id')[:5]
    return render(request, 'dashboard.html', {
        'stats': get_stats(),
        'recent_bookings': recent_bookings,
    })


@login_required(login_url='/login/')
def rooms_page(request):
    return render(request, 'rooms.html', {
        'rooms': Room.objects.all().order_by('room_number'),
        'festive': SiteSetting.get().festive_mode,
        'available_rooms': Room.objects.filter(status='available').order_by('room_number'),
        'maintenance_rooms': Room.objects.filter(status='maintenance').order_by('room_number'),
    })


@login_required(login_url='/login/')
def guests_page(request):
    return render(request, 'guests.html', {
        'guests': Guest.objects.all().order_by('name'),
    })


@login_required(login_url='/login/')
def bookings_page(request):
    return render(request, 'bookings.html', {
        'bookings': Booking.objects.select_related('guest', 'room').order_by('-id'),
        'guests': Guest.objects.all().order_by('name'),
        'rooms': Room.objects.all().order_by('room_number'),
    })


# ── Live Stats API ─────────────────────────────────────────────────────────────

def api_stats(request):
    return JsonResponse(get_stats())


ROOM_RANGES = {
    'standard': range(101, 200),
    'deluxe':   range(201, 300),
    'suite':    range(301, 351),
}


@login_required(login_url='/login/')
def toggle_festive(request):
    if request.method == 'POST':
        s = SiteSetting.get()
        s.festive_mode = not s.festive_mode
        s.save()
        return JsonResponse({'festive': s.festive_mode})
    return JsonResponse({'error': 'POST only'}, status=405)


@login_required(login_url='/login/')
def next_room_number(request):
    room_type = request.GET.get('type', '')
    if room_type not in ROOM_RANGES:
        return JsonResponse({'error': 'Invalid type'}, status=400)
    taken = set(Room.objects.values_list('room_number', flat=True))
    for n in ROOM_RANGES[room_type]:
        if str(n) not in taken:
            return JsonResponse({'number': str(n)})
    return JsonResponse({'error': f'All {room_type} room numbers (range full)'}, status=400)


@login_required(login_url='/login/')
def available_room_numbers(request):
    room_type = request.GET.get('type', '')
    exclude_id = request.GET.get('exclude')
    taken = set(Room.objects.values_list('room_number', flat=True))
    if exclude_id:
        try:
            taken.discard(Room.objects.get(id=exclude_id).room_number)
        except Room.DoesNotExist:
            pass
    if room_type in ROOM_RANGES:
        pool = [str(n) for n in ROOM_RANGES[room_type] if str(n) not in taken]
    else:
        pool = []
        for r in ROOM_RANGES.values():
            pool.extend(str(n) for n in r if str(n) not in taken)
    return JsonResponse({'numbers': pool})


@login_required(login_url='/login/')
def toggle_maintenance(request, room_id):
    if request.method == 'POST':
        from datetime import date
        room = get_object_or_404(Room, id=room_id)
        if room.status == 'occupied':
            return JsonResponse({'error': 'Cannot change an occupied room to maintenance'}, status=400)

        going_maintenance = (room.status == 'available')
        room.status = 'maintenance' if going_maintenance else 'available'
        room.save()

        reassigned = []
        warnings = []
        if going_maintenance:
            today = date.today()
            affected = Booking.objects.filter(
                room=room, check_out__gte=today
            ).select_related('guest')
            for booking in affected:
                new_room = Room.objects.filter(
                    status='available', room_type=room.room_type
                ).exclude(id=room.id).first()
                if new_room:
                    old_num = booking.room.room_number
                    booking.room = new_room
                    booking.save()
                    reassigned.append({'guest': booking.guest.name, 'old': old_num, 'new': new_room.room_number})
                    _send_reassignment_email(booking, old_num, new_room.room_number)
                else:
                    warnings.append(f'Booking #{booking.id} ({booking.guest.name}) — no spare {room.room_type} room available')

        return JsonResponse({
            'status': room.status,
            'room_number': room.room_number,
            'room_id': room.id,
            'reassigned': reassigned,
            'warnings': warnings,
        })
    return JsonResponse({'error': 'POST only'}, status=405)


# ── Guest-facing website ───────────────────────────────────────────────────────

def user_home(request):
    festive = SiteSetting.get().festive_mode
    return render(request, 'user/home.html', {
        'available': Room.objects.filter(status='available').count(),
        'featured': _category_data(festive),
        'total_rooms': Room.objects.count(),
        'total_guests': Guest.objects.count(),
        'festive': festive,
    })


def user_rooms(request):
    festive = SiteSetting.get().festive_mode
    return render(request, 'user/rooms.html', {
        'categories': _category_data(festive),
        'festive': festive,
    })


def user_book(request):
    festive = SiteSetting.get().festive_mode
    error = None
    selected_type = request.GET.get('type', '')

    submitted_rooms = []

    if request.method == 'POST':
        from datetime import date
        name = request.POST.get('name', '').strip()
        email_addr = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        check_in_str = request.POST.get('check_in', '').strip()
        check_out_str = request.POST.get('check_out', '').strip()

        try:
            room_count = max(1, min(int(request.POST.get('room_count', 1)), 5))
        except ValueError:
            room_count = 1

        room_configs = []
        for i in range(room_count):
            rtype = request.POST.get(f'room_type_{i}', '').strip()
            try:
                adults = int(request.POST.get(f'adults_{i}', 1))
                children = int(request.POST.get(f'children_{i}', 0))
            except ValueError:
                adults, children = 1, 0
            room_configs.append({'type': rtype, 'adults': adults, 'children': children})

        submitted_rooms = room_configs
        if room_configs:
            selected_type = room_configs[0].get('type', '')

        if not all([name, email_addr, phone, check_in_str, check_out_str]):
            error = 'Please fill in all fields.'
        elif not all(rc['type'] for rc in room_configs):
            error = 'Please select a room type for each room.'
        elif any(rc['adults'] < 1 or rc['adults'] > 2 for rc in room_configs):
            error = 'Each room accommodates 1–2 adults.'
        elif any(rc['children'] > 1 for rc in room_configs):
            error = 'Each room accommodates a maximum of 1 child.'
        else:
            try:
                check_in = date.fromisoformat(check_in_str)
                check_out = date.fromisoformat(check_out_str)
            except ValueError:
                error = 'Invalid dates provided.'
            else:
                nights = (check_out - check_in).days
                if nights <= 0:
                    error = 'Check-out must be after check-in.'
                else:
                    discount = Decimal('0')
                    if festive:
                        discount += Decimal('15')
                    if nights > 5:
                        stay_disc = Decimal(str(round(random.uniform(5, 10), 1)))
                        discount += stay_disc
                    discount = min(discount, Decimal('40'))

                    # Pre-check all rooms before creating any booking
                    rooms_to_assign = []
                    used_ids = []
                    for rc in room_configs:
                        room = Room.objects.filter(
                            status='available', room_type=rc['type']
                        ).exclude(id__in=used_ids).first()
                        if not room:
                            error = f'No {rc["type"]} rooms available right now. Please adjust your selection.'
                            break
                        rooms_to_assign.append(room)
                        used_ids.append(room.id)

                    if not error:
                        group_ref = uuid.uuid4()
                        guest, _ = Guest.objects.get_or_create(
                            email=email_addr, defaults={'name': name, 'phone': phone}
                        )
                        created = []
                        for room, rc in zip(rooms_to_assign, room_configs):
                            b = Booking.objects.create(
                                guest=guest, room=room,
                                check_in=check_in, check_out=check_out,
                                discount_percent=discount,
                                adults=rc['adults'], children=rc['children'],
                                group_ref=group_ref,
                            )
                            room.status = 'occupied'
                            room.save()
                            created.append(b)
                        _send_booking_confirmation(created[0], created)
                        return redirect('user_confirm', booking_id=created[0].id)

    return render(request, 'user/book.html', {
        'categories': _category_data(festive),
        'festive': festive,
        'selected_type': selected_type,
        'error': error,
        'submitted_rooms': submitted_rooms,
    })


def user_confirm(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related('guest', 'room'), id=booking_id
    )
    group_bookings = list(
        Booking.objects.filter(group_ref=booking.group_ref).select_related('room').order_by('id')
    )
    return render(request, 'user/confirm.html', {
        'booking': booking,
        'group_bookings': group_bookings,
    })


def my_bookings(request):
    from datetime import date
    bookings = []
    email = ''
    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if email:
            bookings = list(
                Booking.objects.filter(guest__email=email)
                .select_related('guest', 'room')
                .order_by('-check_in')
            )
            if not bookings:
                error = 'No bookings found for this email address.'
        else:
            error = 'Please enter your email address.'
    return render(request, 'user/my_bookings.html', {
        'bookings': bookings,
        'email': email,
        'error': error,
        'today': date.today(),
    })


def modify_booking(request, booking_id):
    from datetime import date
    booking = get_object_or_404(
        Booking.objects.select_related('guest', 'room'), id=booking_id
    )
    festive = SiteSetting.get().festive_mode
    error = None

    if request.method == 'POST':
        check_in_str = request.POST.get('check_in', '').strip()
        check_out_str = request.POST.get('check_out', '').strip()
        new_type = request.POST.get('room_type', booking.room.room_type).strip()
        try:
            adults = int(request.POST.get('adults', booking.adults))
            children = int(request.POST.get('children', booking.children))
        except ValueError:
            adults, children = booking.adults, booking.children

        if adults < 1 or adults > 2:
            error = 'Each room accommodates 1–2 adults.'
        elif children > 1:
            error = 'Maximum 1 child per room.'
        else:
            try:
                check_in = date.fromisoformat(check_in_str)
                check_out = date.fromisoformat(check_out_str)
            except ValueError:
                error = 'Invalid dates provided.'
            else:
                if (check_out - check_in).days <= 0:
                    error = 'Check-out must be after check-in.'
                else:
                    changes = []

                    if new_type != booking.room.room_type:
                        new_room = Room.objects.filter(
                            status='available', room_type=new_type
                        ).exclude(id=booking.room.id).first()
                        if not new_room:
                            error = f'No {new_type} rooms available right now.'
                        else:
                            changes.append(
                                f'Room type: {booking.room.room_type.capitalize()} → {new_type.capitalize()}'
                            )
                            booking.room.status = 'available'
                            booking.room.save()
                            booking.room = new_room
                            new_room.status = 'occupied'
                            new_room.save()

                    if not error:
                        if check_in != booking.check_in or check_out != booking.check_out:
                            changes.append(
                                f'Dates: {booking.check_in} – {booking.check_out} → {check_in} – {check_out}'
                            )
                        if adults != booking.adults or children != booking.children:
                            changes.append(
                                f'Guests: {booking.adults} adult(s), {booking.children} child(ren) → {adults} adult(s), {children} child(ren)'
                            )
                        booking.check_in = check_in
                        booking.check_out = check_out
                        booking.adults = adults
                        booking.children = children
                        booking.save()
                        if changes:
                            _send_modification_confirmation(booking)
                            _send_admin_modification_notification(booking, changes)
                        return redirect('user_confirm', booking_id=booking.id)

    return render(request, 'user/modify_booking.html', {
        'booking': booking,
        'categories': _category_data(festive),
        'error': error,
    })
