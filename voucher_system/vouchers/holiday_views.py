from django.shortcuts import redirect
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import HolidayBooking, Company, UserPermission, Vehicle, PaymentType, TripSettlement, TripSettlementCharge, BankSettlement, HolidayBankApprover, RepairMaintenance, RepairItem, RepairBankSettlement
from .views import check_user_permission
from decimal import Decimal


def auto_complete_bookings(company_id):
    """Flip CONFIRMED → COMPLETED for any booking whose return date+time has passed."""
    from django.utils import timezone
    import datetime
    now = timezone.localtime(timezone.now())
    candidates = HolidayBooking.objects.filter(
        company_id=company_id,
        status='CONFIRMED',
        return_date__isnull=False,
        return_time__isnull=False,
    )
    done = [
        b.id for b in candidates
        if now >= timezone.make_aware(
            datetime.datetime.combine(b.return_date, b.return_time)
        )
    ]
    if done:
        HolidayBooking.objects.filter(id__in=done).update(status='COMPLETED')


def auto_delete_expired_pending(company_id):
    """Delete PENDING (unconfirmed) bookings whose return date+time has passed.
    Falls back to trip_date end-of-day when no return date/time is set."""
    from django.utils import timezone
    import datetime
    now = timezone.localtime(timezone.now())
    candidates = HolidayBooking.objects.filter(company_id=company_id, status='PENDING')
    to_delete = []
    for b in candidates:
        if b.return_date and b.return_time:
            deadline = timezone.make_aware(datetime.datetime.combine(b.return_date, b.return_time))
        else:
            deadline = timezone.make_aware(
                datetime.datetime.combine(b.trip_date, datetime.time(23, 59, 59))
            )
        if now >= deadline:
            to_delete.append(b.id)
    if to_delete:
        HolidayBooking.objects.filter(id__in=to_delete).delete()


def number_to_words(n):
    try:
        n = int(Decimal(str(n)))
    except Exception:
        return ''
    if n == 0:
        return 'ZERO'
    ones = ['', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE',
            'TEN', 'ELEVEN', 'TWELVE', 'THIRTEEN', 'FOURTEEN', 'FIFTEEN', 'SIXTEEN',
            'SEVENTEEN', 'EIGHTEEN', 'NINETEEN']
    tens_w = ['', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY', 'SIXTY', 'SEVENTY', 'EIGHTY', 'NINETY']

    def below_hundred(x):
        return ones[x] if x < 20 else tens_w[x // 10] + (' ' + ones[x % 10] if x % 10 else '')

    def below_thousand(x):
        if x < 100:
            return below_hundred(x)
        return ones[x // 100] + ' HUNDRED' + (' ' + below_hundred(x % 100) if x % 100 else '')

    parts = []
    if n >= 10000000:
        parts.append(below_thousand(n // 10000000) + ' CRORE'); n %= 10000000
    if n >= 100000:
        parts.append(below_thousand(n // 100000) + ' LAKH'); n %= 100000
    if n >= 1000:
        parts.append(below_thousand(n // 1000) + ' THOUSAND'); n %= 1000
    if n > 0:
        parts.append(below_thousand(n))
    return ' '.join(parts)


class HolidayView(LoginRequiredMixin, TemplateView):
    template_name = 'vouchers/holiday.html'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        if active_company_id:
            try:
                co = Company.objects.get(id=active_company_id)
                if not co.enable_holidays:
                    messages.error(request, 'Holidays module is not enabled for this company.')
                    return redirect('home')
            except Company.DoesNotExist:
                pass
        has_perm, error = check_user_permission(request.user, 'can_view_holiday_list', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_company_id = self.request.session.get('active_company_id')
        if active_company_id:
            try:
                context['company'] = Company.objects.get(id=active_company_id)
            except Company.DoesNotExist:
                context['company'] = None
        perms = (
            UserPermission.get_or_create_for_user(
                self.request.user,
                Company.objects.get(id=active_company_id)
            )
            if active_company_id and not self.request.user.is_superuser
            else None
        )
        context['can_create_holiday'] = self.request.user.is_superuser or (perms and perms.can_create_holiday)
        context['can_edit_holiday']   = self.request.user.is_superuser or (perms and perms.can_edit_holiday)
        context['can_delete_holiday'] = self.request.user.is_superuser or (perms and perms.can_delete_holiday)
        context['is_superuser']       = self.request.user.is_superuser
        context['is_approver']        = HolidayBankApprover.objects.filter(
            user=self.request.user, is_active=True
        ).exists() or self.request.user.is_superuser
        return context


class HolidayDetailView(LoginRequiredMixin, DetailView):
    model = HolidayBooking
    template_name = 'vouchers/holiday_detail.html'
    context_object_name = 'booking'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_view_holiday_detail', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('holiday')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_company_id = self.request.session.get('active_company_id')
        if active_company_id:
            try:
                context['company'] = Company.objects.get(id=active_company_id)
            except Company.DoesNotExist:
                context['company'] = None
        if self.request.user.is_superuser:
            context['can_edit']   = True
            context['can_delete'] = True
        else:
            perms = (
                UserPermission.get_or_create_for_user(
                    self.request.user,
                    Company.objects.get(id=active_company_id)
                ) if active_company_id else None
            )
            context['can_edit']   = bool(perms and perms.can_edit_holiday)
            context['can_delete'] = bool(perms and perms.can_delete_holiday)
        context['is_pending']   = self.object.status == 'PENDING'
        context['is_completed'] = self.object.status == 'COMPLETED'
        is_bank_settled = False
        try:
            is_bank_settled = self.object.settlement.bank.status == BankSettlement.STATUS_APPROVED
        except (TripSettlement.DoesNotExist, BankSettlement.DoesNotExist, AttributeError):
            pass
        context['is_bank_settled'] = is_bank_settled
        return context


class HolidayCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_create_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=400)

        data = request.data
        import re as _re
        contact_number = data.get('contact_number', '')
        if not _re.match(r'^\d{10}$', str(contact_number)):
            return Response({'error': 'Contact number must be exactly 10 digits.'}, status=400)
        second_contact = data.get('second_contact_number')
        if second_contact and not _re.match(r'^\d{10}$', str(second_contact)):
            return Response({'error': 'Contact 2 must be exactly 10 digits.'}, status=400)

        try:
            booked_vehicle = None
            vehicle_id = data.get('booked_vehicle')
            if vehicle_id:
                try:
                    booked_vehicle = Vehicle.objects.get(id=vehicle_id, company=company)
                except Vehicle.DoesNotExist:
                    pass

            booking = HolidayBooking.objects.create(
                company=company,
                trip_date=data['trip_date'],
                purpose_of_booking=data.get('purpose_of_booking', ''),
                booked_by=data['booked_by'],
                contact_number=data['contact_number'],
                second_contact_number=data.get('second_contact_number') or None,
                departure_location=data['departure_location'],
                destination=data['destination'],
                departure_time=data['departure_time'],
                return_date=data.get('return_date') or None,
                return_time=data.get('return_time') or None,
                no_of_passengers=int(data['no_of_passengers']),
                booked_vehicle=booked_vehicle,
                ac_type=data.get('ac_type', 'NON_AC'),
                payment_type_label=data.get('payment_type_label', ''),
                total_rent=Decimal(data.get('total_rent', 0)),
                service_charge=Decimal(data.get('service_charge', 0)) if data.get('service_charge') else Decimal('0'),
                advance_amount=Decimal(data.get('advance_amount', 0)) if data.get('advance_amount') else Decimal('0'),
                max_km=int(data['max_km']) if data.get('max_km') else None,
                extra_km_charge=Decimal(data['extra_km_charge']) if data.get('extra_km_charge') else None,
                special_instructions=data.get('special_instructions', ''),
                status='PENDING',
                created_by=request.user,
            )
            return Response({
                'success': True,
                'booking_number': booking.booking_number,
                'id': booking.id,
                'message': f'Holiday booking {booking.booking_number} created successfully!'
            }, status=201)
        except KeyError as e:
            return Response({'error': f'Missing field: {e}'}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class HolidayBookedDatesAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company'}, status=400)

        auto_complete_bookings(active_company_id)
        auto_delete_expired_pending(active_company_id)

        bookings = HolidayBooking.objects.filter(
            company_id=active_company_id,
            status__in=['PENDING', 'CONFIRMED', 'COMPLETED']
        ).values('trip_date', 'return_date', 'return_time', 'booking_number', 'destination',
                 'status', 'id', 'departure_time', 'booked_vehicle__name')

        events = []
        for b in bookings:
            vehicle    = b['booked_vehicle__name'] or ''
            time_label = b['departure_time'].strftime('%I:%M %p') if b['departure_time'] else ''
            label      = f"{vehicle}  {time_label}".strip() if vehicle else time_label
            events.append({
                'id':     b['id'],
                'title':  f"{b['booking_number']} – {b['destination']}",
                'label':  label,
                'status': b['status'],
                'start':  b['trip_date'].isoformat(),
                'end':    b['return_date'].isoformat() if b['return_date'] else None,
            })
        return Response({'events': events})


class HolidayListByDateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.GET.get('date')
        active_company_id = request.session.get('active_company_id')
        if not date_str or not active_company_id:
            return Response({'bookings': []})

        try:
            from datetime import datetime
            trip_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format'}, status=400)

        bookings = HolidayBooking.objects.filter(
            company_id=active_company_id,
            trip_date=trip_date
        ).select_related('created_by', 'booked_vehicle')

        data = [{
            'id': b.id,
            'booking_number': b.booking_number,
            'destination': b.destination,
            'departure_location': b.departure_location,
            'departure_time': b.departure_time.strftime('%H:%M'),
            'return_time': b.return_time.strftime('%H:%M') if b.return_time else None,
            'ac_type': b.get_ac_type_display(),
            'no_of_passengers': b.no_of_passengers,
            'booked_by': b.booked_by,
            'contact_number': b.contact_number,
            'total_amount': str(b.total_amount),
            'status': b.status,
            'booked_vehicle': str(b.booked_vehicle) if b.booked_vehicle else None,
        } for b in bookings]

        return Response({'bookings': data})


class HolidayDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_delete_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=active_company_id)
            # Block deletion if bank settlement is approved
            try:
                if booking.settlement.bank.status == BankSettlement.STATUS_APPROVED:
                    return Response({'error': 'Cannot delete an approved order form.'}, status=400)
            except (TripSettlement.DoesNotExist, BankSettlement.DoesNotExist, AttributeError):
                pass
            booking.delete()
            return Response({'success': True, 'message': 'Booking deleted'})
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)


class HolidayUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=active_company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        if booking.status == 'COMPLETED':
            return Response({'error': 'Completed trips cannot be edited.'}, status=400)
        try:
            if booking.settlement.bank.status == BankSettlement.STATUS_APPROVED:
                return Response({'error': 'Bank-settled trips cannot be edited.'}, status=400)
        except (TripSettlement.DoesNotExist, BankSettlement.DoesNotExist, AttributeError):
            pass

        data = request.data
        import re as _re
        contact_number = data.get('contact_number', '')
        if not _re.match(r'^\d{10}$', str(contact_number)):
            return Response({'error': 'Contact number must be exactly 10 digits.'}, status=400)
        second_contact = data.get('second_contact_number')
        if second_contact and not _re.match(r'^\d{10}$', str(second_contact)):
            return Response({'error': 'Contact 2 must be exactly 10 digits.'}, status=400)

        try:
            booked_vehicle = None
            vehicle_id = data.get('booked_vehicle')
            if vehicle_id:
                try:
                    company = Company.objects.get(id=active_company_id)
                    booked_vehicle = Vehicle.objects.get(id=vehicle_id, company=company)
                except (Vehicle.DoesNotExist, Company.DoesNotExist):
                    pass

            booking.trip_date = data['trip_date']
            booking.purpose_of_booking = data.get('purpose_of_booking', '')
            booking.booked_by = data['booked_by']
            booking.contact_number = data['contact_number']
            booking.second_contact_number = data.get('second_contact_number') or None
            booking.departure_location = data['departure_location']
            booking.destination = data['destination']
            booking.departure_time = data['departure_time']
            booking.return_date = data.get('return_date') or None
            booking.return_time = data.get('return_time') or None
            booking.no_of_passengers = int(data['no_of_passengers'])
            booking.booked_vehicle = booked_vehicle
            booking.ac_type = data.get('ac_type', 'NON_AC')
            booking.payment_type_label = data.get('payment_type_label', '')
            booking.total_rent = Decimal(data.get('total_rent', 0))
            booking.service_charge = Decimal(data.get('service_charge', 0)) if data.get('service_charge') else Decimal('0')
            booking.advance_amount = Decimal(data.get('advance_amount', 0)) if data.get('advance_amount') else Decimal('0')
            booking.max_km = int(data['max_km']) if data.get('max_km') else None
            booking.extra_km_charge = Decimal(data['extra_km_charge']) if data.get('extra_km_charge') else None
            booking.special_instructions = data.get('special_instructions', '')
            booking.save()
            return Response({'success': True, 'message': f'Booking {booking.booking_number} updated successfully!'})
        except KeyError as e:
            return Response({'error': f'Missing field: {e}'}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class HolidayConfirmAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=active_company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)
        if booking.status != 'PENDING':
            return Response({'error': 'Only pending enquiries can be confirmed.'}, status=400)

        # Vehicle conflict check: reject if the same vehicle is already confirmed for an overlapping date range
        if booking.booked_vehicle_id:
            b_start = booking.trip_date
            b_end   = booking.return_date or booking.trip_date
            conflicts = HolidayBooking.objects.filter(
                company_id=active_company_id,
                booked_vehicle_id=booking.booked_vehicle_id,
                status='CONFIRMED',
            ).exclude(pk=booking.pk)
            for existing in conflicts:
                e_start = existing.trip_date
                e_end   = existing.return_date or existing.trip_date
                if b_start <= e_end and b_end >= e_start:
                    return Response({
                        'error': (
                            f'{booking.booked_vehicle.name} is already booked for '
                            f'{existing.booking_number} '
                            f'({e_start.strftime("%d %b %Y")} – {e_end.strftime("%d %b %Y")}). '
                            f'Change the vehicle or adjust the dates before confirming.'
                        )
                    }, status=400)

        # Update advance amount if provided (recalculates balance_amount via model save)
        advance_raw = request.data.get('advance_amount')
        if advance_raw not in (None, ''):
            try:
                from decimal import Decimal as _D
                advance = _D(str(advance_raw))
                if advance < 0:
                    return Response({'error': 'Advance amount cannot be negative.'}, status=400)
                if advance > booking.total_amount:
                    return Response({'error': 'Advance amount cannot exceed total amount.'}, status=400)
                booking.advance_amount = advance
            except Exception:
                return Response({'error': 'Invalid advance amount.'}, status=400)

        booking.status = 'CONFIRMED'
        booking.save()  # full save so balance_amount recalculates
        return Response({'success': True, 'message': f'Booking {booking.booking_number} confirmed!'})


# =============================================
# VEHICLE MASTER APIs
# =============================================

class VehicleListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'vehicles': []})
        show_all = request.GET.get('all') == '1'
        qs = Vehicle.objects.filter(company_id=active_company_id)
        if not show_all:
            qs = qs.filter(is_active=True)
        data = [{
            'id': v.id,
            'name': v.name,
            'registration_number': v.registration_number,
            'batta_percentage': str(v.batta_percentage) if v.batta_percentage is not None else None,
            'is_active': v.is_active,
        } for v in qs]
        return Response({'vehicles': data})


class VehicleCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company'}, status=400)
        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=400)

        name = request.data.get('name', '').strip().upper()
        reg_number = request.data.get('registration_number', '').strip().upper()
        if not name or not reg_number:
            return Response({'error': 'Vehicle name and registration number are required'}, status=400)

        if Vehicle.objects.filter(company=company, registration_number=reg_number).exists():
            return Response({'error': 'A vehicle with this registration number already exists'}, status=400)

        batta_raw = request.data.get('batta_percentage')
        batta_percentage = Decimal(str(batta_raw)) if batta_raw not in (None, '', 0, '0') else None

        vehicle = Vehicle.objects.create(
            company=company,
            name=name,
            registration_number=reg_number,
            batta_percentage=batta_percentage,
            created_by=request.user,
        )
        return Response({
            'success': True,
            'id': vehicle.id,
            'name': vehicle.name,
            'registration_number': vehicle.registration_number,
            'batta_percentage': str(vehicle.batta_percentage) if vehicle.batta_percentage is not None else None,
            'message': f'Vehicle {vehicle.name} added successfully!'
        }, status=201)


class VehicleToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        active_company_id = request.session.get('active_company_id')
        try:
            vehicle = Vehicle.objects.get(pk=pk, company_id=active_company_id)
            vehicle.is_active = not vehicle.is_active
            vehicle.save(update_fields=['is_active'])
            state = 'enabled' if vehicle.is_active else 'disabled'
            return Response({'success': True, 'is_active': vehicle.is_active, 'message': f'Vehicle {state}.'})
        except Vehicle.DoesNotExist:
            return Response({'error': 'Vehicle not found'}, status=404)


class VehicleUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        active_company_id = request.session.get('active_company_id')
        try:
            vehicle = Vehicle.objects.get(pk=pk, company_id=active_company_id)
        except Vehicle.DoesNotExist:
            return Response({'error': 'Vehicle not found'}, status=404)

        name = request.data.get('name', '').strip().upper()
        reg_number = request.data.get('registration_number', '').strip().upper()
        if not name or not reg_number:
            return Response({'error': 'Vehicle name and registration number are required'}, status=400)

        dup = Vehicle.objects.filter(company_id=active_company_id, registration_number=reg_number).exclude(pk=pk)
        if dup.exists():
            return Response({'error': 'Another vehicle with this registration number already exists'}, status=400)

        batta_raw = request.data.get('batta_percentage')
        vehicle.name = name
        vehicle.registration_number = reg_number
        vehicle.batta_percentage = Decimal(str(batta_raw)) if batta_raw not in (None, '', '0', 0) else None
        vehicle.save(update_fields=['name', 'registration_number', 'batta_percentage'])
        return Response({'success': True, 'message': 'Vehicle updated successfully.'})


# =============================================
# PAYMENT TYPE MASTER APIs
# =============================================

class PaymentTypeListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'payment_types': []})
        show_all = request.GET.get('all') == '1'
        qs = PaymentType.objects.filter(company_id=active_company_id)
        if not show_all:
            qs = qs.filter(is_active=True)
        data = [{'id': pt.id, 'name': pt.name, 'is_active': pt.is_active} for pt in qs]
        return Response({'payment_types': data})


class PaymentTypeCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company'}, status=400)
        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=400)

        name = request.data.get('name', '').strip().upper()
        if not name:
            return Response({'error': 'Payment type name is required'}, status=400)

        if PaymentType.objects.filter(company=company, name=name).exists():
            return Response({'error': 'This payment type already exists'}, status=400)

        pt = PaymentType.objects.create(company=company, name=name, created_by=request.user)
        return Response({'success': True, 'id': pt.id, 'name': pt.name, 'message': f'{pt.name} added successfully!'}, status=201)


class PaymentTypeToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        active_company_id = request.session.get('active_company_id')
        try:
            pt = PaymentType.objects.get(pk=pk, company_id=active_company_id)
            pt.is_active = not pt.is_active
            pt.save(update_fields=['is_active'])
            state = 'enabled' if pt.is_active else 'disabled'
            return Response({'success': True, 'is_active': pt.is_active, 'message': f'Payment type {state}.'})
        except PaymentType.DoesNotExist:
            return Response({'error': 'Payment type not found'}, status=404)


class PaymentTypeUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        active_company_id = request.session.get('active_company_id')
        try:
            pt = PaymentType.objects.get(pk=pk, company_id=active_company_id)
        except PaymentType.DoesNotExist:
            return Response({'error': 'Payment type not found'}, status=404)

        name = request.data.get('name', '').strip().upper()
        if not name:
            return Response({'error': 'Payment type name is required'}, status=400)

        if PaymentType.objects.filter(company_id=active_company_id, name=name).exclude(pk=pk).exists():
            return Response({'error': 'This payment type name already exists'}, status=400)

        pt.name = name
        pt.save(update_fields=['name'])
        return Response({'success': True, 'message': 'Payment type updated successfully.'})


# =============================================
# TRIP SETTLEMENT
# =============================================

class TripSettlementView(LoginRequiredMixin, TemplateView):
    template_name = 'vouchers/trip_settlement.html'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_view_holiday_list', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_company_id = self.request.session.get('active_company_id')
        if active_company_id:
            try:
                context['company'] = Company.objects.get(id=active_company_id)
            except Company.DoesNotExist:
                context['company'] = None
        return context


class HolidayCompletedListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'bookings': []})

        auto_complete_bookings(active_company_id)

        bookings = HolidayBooking.objects.filter(
            company_id=active_company_id,
            status='COMPLETED',
        ).select_related('booked_vehicle', 'created_by').order_by('-return_date', '-return_time')

        settlement_map = {
            s.booking_id: s.id
            for s in TripSettlement.objects.filter(booking__company_id=active_company_id)
        }

        completed = []
        for b in bookings:
                s_id = settlement_map.get(b.id)
                completed.append({
                    'id': b.id,
                    'booking_number': b.booking_number,
                    'trip_date': b.trip_date.isoformat(),
                    'return_date': b.return_date.isoformat(),
                    'return_time': b.return_time.strftime('%H:%M'),
                    'destination': b.destination,
                    'departure_location': b.departure_location,
                    'departure_time': b.departure_time.strftime('%H:%M'),
                    'booked_by': b.booked_by,
                    'contact_number': b.contact_number,
                    'second_contact_number': b.second_contact_number or '',
                    'purpose_of_booking': b.purpose_of_booking or '',
                    'payment_type_label': b.payment_type_label or '',
                    'no_of_passengers': b.no_of_passengers,
                    'ac_type': b.ac_type,
                    'booked_vehicle_id': b.booked_vehicle_id or '',
                    'booked_vehicle': str(b.booked_vehicle) if b.booked_vehicle else '',
                    'booked_vehicle_batta': str(b.booked_vehicle.batta_percentage) if b.booked_vehicle and b.booked_vehicle.batta_percentage else '0',
                    'max_km': b.max_km or '',
                    'extra_km_charge': str(b.extra_km_charge) if b.extra_km_charge else '',
                    'total_rent': str(b.total_rent),
                    'service_charge': str(b.service_charge or 0),
                    'advance_amount': str(b.advance_amount or 0),
                    'total_amount': str(b.total_amount),
                    'balance_amount': str(b.balance_amount or 0),
                    'special_instructions': b.special_instructions or '',
                    'status': b.status,
                    'has_settlement': s_id is not None,
                    'settlement_id': s_id,
                })

        return Response({'bookings': completed})


class HolidayCompletedCountAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'count': 0})

        auto_complete_bookings(active_company_id)
        count = HolidayBooking.objects.filter(
            company_id=active_company_id,
            status='COMPLETED',
        ).count()
        return Response({'count': count})


# =============================================
# TRIP SETTLEMENT APIs
# =============================================

class TripSettlementGetAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=active_company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        try:
            s = booking.settlement
            custom = [
                {
                    'id': c.id,
                    'name': c.name,
                    'amount': str(c.amount),
                    'attachment_url': request.build_absolute_uri(c.attachment.url) if c.attachment else None,
                    'attachment_name': c.attachment.name.split('/')[-1] if c.attachment else None,
                }
                for c in s.custom_charges.all()
            ]
            try:
                bank_is_approved = s.bank.status == BankSettlement.STATUS_APPROVED
            except BankSettlement.DoesNotExist:
                bank_is_approved = False

            return Response({
                'exists': True,
                'bank_is_approved': bank_is_approved,
                'commission_percentage': str(s.commission_percentage),
                'commission_amount': str(s.commission_amount),
                'net_rent': str(s.net_rent),
                'batta_percentage': str(s.batta_percentage),
                'batta_amount': str(s.batta_amount),
                'diesel_charge': str(s.diesel_charge),
                'diesel_bill_url': request.build_absolute_uri(s.diesel_bill.url) if s.diesel_bill else None,
                'diesel_bill_name': s.diesel_bill.name.split('/')[-1] if s.diesel_bill else None,
                'cleaning_charge': str(s.cleaning_charge),
                'grease_charge': str(s.grease_charge),
                'grease_bill_url': request.build_absolute_uri(s.grease_bill.url) if s.grease_bill else None,
                'grease_bill_name': s.grease_bill.name.split('/')[-1] if s.grease_bill else None,
                'net_balance': str(s.net_balance),
                'custom_charges': custom,
            })
        except TripSettlement.DoesNotExist:
            return Response({'exists': False})


class TripSettlementSaveAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=active_company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        # block edits if bank already approved
        try:
            if booking.settlement.bank.status == BankSettlement.STATUS_APPROVED:
                return Response({'error': 'This settlement has been bank-approved and cannot be edited.'}, status=403)
        except (TripSettlement.DoesNotExist, BankSettlement.DoesNotExist):
            pass

        data = request.data
        files = request.FILES

        commission_pct  = Decimal(data.get('commission_percentage', '0') or '0')
        diesel_charge   = Decimal(data.get('diesel_charge', '0') or '0')
        cleaning_charge = Decimal(data.get('cleaning_charge', '0') or '0')
        grease_charge   = Decimal(data.get('grease_charge', '0') or '0')

        total_amount     = Decimal(booking.total_amount or 0)
        commission_amt   = (total_amount * commission_pct / Decimal('100')).quantize(Decimal('0.01'))
        net_rent         = total_amount - commission_amt

        # batta from vehicle
        batta_pct = Decimal(data.get('batta_percentage', '0') or '0')
        batta_amt = (net_rent * batta_pct / Decimal('100')).quantize(Decimal('0.01'))

        # custom charges
        custom_count = int(data.get('custom_count', 0) or 0)
        custom_total = Decimal('0')
        custom_rows = []
        for i in range(custom_count):
            name   = data.get(f'custom_name_{i}', '').strip()
            amount = Decimal(data.get(f'custom_amount_{i}', '0') or '0')
            file   = files.get(f'custom_file_{i}')
            if name:
                custom_total += amount
                custom_rows.append((i, name, amount, file))

        net_balance = net_rent - batta_amt - diesel_charge - cleaning_charge - grease_charge - custom_total

        # get or create settlement
        try:
            settlement = booking.settlement
        except TripSettlement.DoesNotExist:
            settlement = TripSettlement(booking=booking, created_by=request.user)

        settlement.commission_percentage = commission_pct
        settlement.commission_amount     = commission_amt
        settlement.net_rent              = net_rent
        settlement.batta_percentage      = batta_pct
        settlement.batta_amount          = batta_amt
        settlement.diesel_charge         = diesel_charge
        settlement.cleaning_charge       = cleaning_charge
        settlement.grease_charge         = grease_charge
        settlement.net_balance           = net_balance

        if 'diesel_bill' in files:
            settlement.diesel_bill = files['diesel_bill']
        if 'grease_bill' in files:
            settlement.grease_bill = files['grease_bill']

        settlement.save()

        # rebuild custom charges (delete old, recreate)
        settlement.custom_charges.all().delete()
        for (i, name, amount, file) in custom_rows:
            charge = TripSettlementCharge(settlement=settlement, name=name.upper(), amount=amount)
            if file:
                charge.attachment = file
            charge.save()

        return Response({'success': True, 'message': 'Settlement saved successfully!'})


# =============================================
# BANK SETTLEMENT
# =============================================

class BankView(LoginRequiredMixin, TemplateView):
    template_name = 'vouchers/bank_settlement.html'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_view_holiday_list', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_company_id = self.request.session.get('active_company_id')
        perms = (
            UserPermission.get_or_create_for_user(
                self.request.user,
                Company.objects.get(id=active_company_id)
            ) if active_company_id and not self.request.user.is_superuser else None
        )
        context['is_superuser']       = self.request.user.is_superuser
        context['can_edit_holiday']   = self.request.user.is_superuser or (perms and perms.can_edit_holiday)
        context['can_delete_holiday'] = self.request.user.is_superuser or (perms and perms.can_delete_holiday)
        context['is_approver']  = HolidayBankApprover.objects.filter(
            user=self.request.user, is_active=True
        ).exists() or self.request.user.is_superuser
        return context


class BankListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'entries': []})

        settlements = TripSettlement.objects.filter(
            booking__company_id=active_company_id
        ).select_related(
            'booking', 'booking__booked_vehicle', 'bank', 'bank__approved_by'
        ).order_by('-booking__trip_date')

        entries = []
        for i, s in enumerate(settlements, 1):
            b = s.booking
            try:
                bank = s.bank
                bank_data = {
                    'id': bank.id,
                    'document_url': request.build_absolute_uri(bank.bank_document.url),
                    'document_name': bank.bank_document.name.split('/')[-1],
                    'status': bank.status,
                    'approved_by': bank.approved_by.get_full_name() or bank.approved_by.username if bank.approved_by else None,
                    'approved_at': bank.approved_at.strftime('%d %b %Y, %H:%M') if bank.approved_at else None,
                }
            except BankSettlement.DoesNotExist:
                bank_data = None

            entries.append({
                'sl': i,
                'settlement_id': s.id,
                'booking_id': b.id,
                'booking_number': b.booking_number,
                'booked_by': b.booked_by,
                'vehicle': str(b.booked_vehicle) if b.booked_vehicle else '—',
                'net_balance': str(s.net_balance),
                'bank': bank_data,
            })
        return Response({'entries': entries})


class BankDocumentUploadAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, settlement_pk):
        active_company_id = request.session.get('active_company_id')
        try:
            settlement = TripSettlement.objects.get(
                pk=settlement_pk, booking__company_id=active_company_id
            )
        except TripSettlement.DoesNotExist:
            return Response({'error': 'Settlement not found'}, status=404)

        doc = request.FILES.get('bank_document')
        if not doc:
            return Response({'error': 'No document uploaded'}, status=400)

        try:
            bank = settlement.bank
            bank.bank_document = doc
            bank.status = BankSettlement.STATUS_PENDING
            bank.save(update_fields=['bank_document', 'status', 'updated_at'])
        except BankSettlement.DoesNotExist:
            bank = BankSettlement.objects.create(
                settlement=settlement,
                bank_document=doc,
                status=BankSettlement.STATUS_PENDING,
                submitted_by=request.user,
            )
        return Response({'success': True, 'message': 'Document uploaded. Pending approval.'})


class BankApproveAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, bank_pk):
        active_company_id = request.session.get('active_company_id')
        is_approver = HolidayBankApprover.objects.filter(
            company_id=active_company_id, user=request.user, is_active=True
        ).exists()
        if not request.user.is_superuser and not is_approver:
            return Response({'error': 'You do not have approval permission'}, status=403)
        try:
            bank = BankSettlement.objects.get(pk=bank_pk)
        except BankSettlement.DoesNotExist:
            return Response({'error': 'Bank settlement not found'}, status=404)

        from django.utils import timezone
        bank.status      = BankSettlement.STATUS_APPROVED
        bank.approved_by = request.user
        bank.approved_at = timezone.now()
        bank.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        return Response({'success': True, 'message': 'Settlement approved.'})


# =============================================
# HOLIDAY BANK APPROVAL MASTER APIs
# =============================================

class BankApproverListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'approvers': [], 'available_users': []})

        approvers = HolidayBankApprover.objects.filter(
            company_id=active_company_id
        ).select_related('user')

        approver_user_ids = set(a.user_id for a in approvers)

        # All company members not yet added as approvers
        from .models import CompanyMembership
        members = CompanyMembership.objects.filter(
            company_id=active_company_id, is_active=True
        ).select_related('user').exclude(user_id__in=approver_user_ids)

        return Response({
            'approvers': [
                {
                    'id': a.id,
                    'user_id': a.user_id,
                    'username': a.user.username,
                    'full_name': a.user.get_full_name() or a.user.username,
                    'is_active': a.is_active,
                }
                for a in approvers
            ],
            'available_users': [
                {
                    'id': m.user.id,
                    'username': m.user.username,
                    'full_name': m.user.get_full_name() or m.user.username,
                }
                for m in members
            ],
        })


class BankApproverAddAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company'}, status=400)

        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'User is required'}, status=400)

        try:
            from django.contrib.auth.models import User as AuthUser
            company = Company.objects.get(id=active_company_id)
            user = AuthUser.objects.get(id=user_id)
        except (Company.DoesNotExist, AuthUser.DoesNotExist):
            return Response({'error': 'Invalid company or user'}, status=400)

        obj, created = HolidayBankApprover.objects.get_or_create(
            company=company, user=user,
            defaults={'created_by': request.user, 'is_active': True}
        )
        if not created and not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=['is_active'])

        return Response({'success': True, 'message': f'{user.username} added as approver.'}, status=201)


class BankApproverToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)
        try:
            approver = HolidayBankApprover.objects.get(pk=pk)
            approver.is_active = not approver.is_active
            approver.save(update_fields=['is_active'])
            state = 'enabled' if approver.is_active else 'disabled'
            return Response({'success': True, 'is_active': approver.is_active, 'message': f'Approver {state}.'})
        except HolidayBankApprover.DoesNotExist:
            return Response({'error': 'Approver not found'}, status=404)


class HolidayPrintView(LoginRequiredMixin, DetailView):
    model = HolidayBooking
    template_name = 'vouchers/holiday_print.html'
    context_object_name = 'booking'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_view_holiday_detail', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('holiday')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_company_id = self.request.session.get('active_company_id')
        if active_company_id:
            try:
                context['company'] = Company.objects.get(id=active_company_id)
            except Company.DoesNotExist:
                context['company'] = None
        booking = self.object
        context['balance_in_words'] = number_to_words(booking.balance_amount or 0)
        return context


# =============================================
# REPAIR & MAINTENANCE APIs
# =============================================

class RepairListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'repairs': []})

        repairs = RepairMaintenance.objects.filter(
            company_id=active_company_id
        ).prefetch_related('items').select_related('vehicle').order_by('-created_at')

        data = []
        for r in repairs:
            data.append({
                'id': r.id,
                'repair_number': r.repair_number,
                'vehicle': str(r.vehicle) if r.vehicle else '—',
                'status': r.status,
                'total_amount': str(r.total_amount),
                'created_at': r.created_at.strftime('%d %b %Y'),
                'items_count': r.items.count(),
            })
        return Response({'repairs': data})


class RepairCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company'}, status=400)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=400)

        data = request.data
        files = request.FILES

        vehicle = None
        vehicle_id = data.get('vehicle_id')
        if vehicle_id:
            try:
                vehicle = Vehicle.objects.get(id=vehicle_id, company=company)
            except Vehicle.DoesNotExist:
                pass

        # KM fields — mandatory
        starting_km_raw = data.get('starting_km', '').strip()
        ending_km_raw   = data.get('ending_km', '').strip()
        starting_km_file = files.get('starting_km_attachment')
        ending_km_file   = files.get('ending_km_attachment')

        if not starting_km_raw:
            return Response({'error': 'Starting KM is required.'}, status=400)
        if not starting_km_file:
            return Response({'error': 'Starting KM attachment is required.'}, status=400)
        if not ending_km_raw:
            return Response({'error': 'Ending KM is required.'}, status=400)
        if not ending_km_file:
            return Response({'error': 'Ending KM attachment is required.'}, status=400)

        try:
            starting_km = int(starting_km_raw)
            ending_km   = int(ending_km_raw)
        except ValueError:
            return Response({'error': 'KM values must be whole numbers.'}, status=400)

        # Collect items
        items = []
        idx = 0
        while True:
            name = data.get(f'item_name_{idx}')
            if not name:
                break
            amount_raw = data.get(f'item_amount_{idx}', '0') or '0'
            try:
                amount = Decimal(str(amount_raw))
            except Exception:
                amount = Decimal('0')
            items.append({
                'name': name,
                'description': data.get(f'item_description_{idx}', ''),
                'amount': amount,
                'file': files.get(f'item_attachment_{idx}'),
            })
            idx += 1

        if not items:
            return Response({'error': 'At least one repair item is required'}, status=400)

        total_amount = sum(item['amount'] for item in items)

        try:
            repair = RepairMaintenance.objects.create(
                company=company,
                vehicle=vehicle,
                notes=data.get('notes', ''),
                total_amount=total_amount,
                starting_km=starting_km,
                starting_km_attachment=starting_km_file,
                ending_km=ending_km,
                ending_km_attachment=ending_km_file,
                created_by=request.user,
            )

            for item in items:
                ri = RepairItem(
                    repair=repair,
                    name=item['name'],
                    description=item['description'],
                    amount=item['amount'],
                )
                if item['file']:
                    ri.attachment = item['file']
                ri.save()

            return Response({
                'success': True,
                'repair_number': repair.repair_number,
                'id': repair.id,
            }, status=201)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class RepairDetailAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=active_company_id)
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found'}, status=404)

        items = []
        for item in repair.items.all():
            items.append({
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'amount': str(item.amount),
                'attachment_url': request.build_absolute_uri(item.attachment.url) if item.attachment else None,
            })

        return Response({
            'repair': {
                'id': repair.id,
                'repair_number': repair.repair_number,
                'vehicle': str(repair.vehicle) if repair.vehicle else '—',
                'vehicle_id': repair.vehicle_id,
                'status': repair.status,
                'total_amount': str(repair.total_amount),
                'notes': repair.notes,
                'starting_km': repair.starting_km,
                'starting_km_attachment_url': request.build_absolute_uri(repair.starting_km_attachment.url) if repair.starting_km_attachment else None,
                'ending_km': repair.ending_km,
                'ending_km_attachment_url': request.build_absolute_uri(repair.ending_km_attachment.url) if repair.ending_km_attachment else None,
                'created_at': repair.created_at.strftime('%d %b %Y'),
                'items': items,
            }
        })


class RepairBankSubmitAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=active_company_id)
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found'}, status=404)

        doc = request.FILES.get('bank_document')

        try:
            bank = repair.bank
            if doc:
                bank.bank_document = doc
            bank.status = RepairBankSettlement.STATUS_PENDING
            bank.save()
        except RepairBankSettlement.DoesNotExist:
            bank = RepairBankSettlement.objects.create(
                repair=repair,
                bank_document=doc,
                status=RepairBankSettlement.STATUS_PENDING,
                submitted_by=request.user,
            )

        repair.status = RepairMaintenance.STATUS_SUBMITTED
        repair.save(update_fields=['status', 'updated_at'])

        return Response({'success': True})


class RepairBankApproveAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        is_approver = HolidayBankApprover.objects.filter(
            company_id=active_company_id, user=request.user, is_active=True
        ).exists()
        if not request.user.is_superuser and not is_approver:
            return Response({'error': 'You do not have approval permission'}, status=403)

        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=active_company_id)
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found'}, status=404)

        try:
            bank = repair.bank
        except RepairBankSettlement.DoesNotExist:
            return Response({'error': 'No bank settlement found for this repair'}, status=404)

        from django.utils import timezone
        bank.status = RepairBankSettlement.STATUS_APPROVED
        bank.approved_by = request.user
        bank.approved_at = timezone.now()
        bank.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

        repair.status = RepairMaintenance.STATUS_APPROVED
        repair.save(update_fields=['status', 'updated_at'])

        return Response({'success': True})


class RepairBankDocumentUploadAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=active_company_id)
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found'}, status=404)

        doc = request.FILES.get('bank_document')
        if not doc:
            return Response({'error': 'No document uploaded'}, status=400)

        try:
            bank = repair.bank
            bank.bank_document = doc
            bank.status = RepairBankSettlement.STATUS_PENDING
            bank.save(update_fields=['bank_document', 'status', 'updated_at'])
        except RepairBankSettlement.DoesNotExist:
            bank = RepairBankSettlement.objects.create(
                repair=repair,
                bank_document=doc,
                status=RepairBankSettlement.STATUS_PENDING,
                submitted_by=request.user,
            )

        repair.status = RepairMaintenance.STATUS_SUBMITTED
        repair.save(update_fields=['status', 'updated_at'])

        return Response({'success': True, 'message': 'Document uploaded. Pending approval.'})


class RepairListForBankAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'pending': [], 'pending_approval': [], 'approved': []})

        repairs = RepairMaintenance.objects.filter(
            company_id=active_company_id
        ).select_related('vehicle', 'created_by').prefetch_related('items').order_by('-created_at')

        pending = []
        pending_approval = []
        approved = []

        for r in repairs:
            try:
                bank = r.bank
                bank_id = bank.id
                bank_status = bank.status
                bank_doc_url = request.build_absolute_uri(bank.bank_document.url) if bank.bank_document else None
                approved_by = bank.approved_by.get_full_name() or bank.approved_by.username if bank.approved_by else None
                approved_at = bank.approved_at.strftime('%d %b %Y, %H:%M') if bank.approved_at else None
            except RepairBankSettlement.DoesNotExist:
                bank_id = None
                bank_status = None
                bank_doc_url = None
                approved_by = None
                approved_at = None

            entry = {
                'id': r.id,
                'repair_number': r.repair_number,
                'vehicle': str(r.vehicle) if r.vehicle else '—',
                'total_amount': str(r.total_amount),
                'status': r.status,
                'bank_id': bank_id,
                'bank_status': bank_status,
                'bank_document_url': bank_doc_url,
                'approved_by': approved_by,
                'approved_at': approved_at,
                'items_count': r.items.count(),
                'created_at': r.created_at.strftime('%d %b %Y'),
            }

            if r.status == RepairMaintenance.STATUS_APPROVED:
                approved.append(entry)
            elif r.status == RepairMaintenance.STATUS_SUBMITTED:
                pending_approval.append(entry)
            else:
                # DRAFT — only include if no bank settlement yet
                pending.append(entry)

        return Response({
            'pending': pending,
            'pending_approval': pending_approval,
            'approved': approved,
        })


class RepairDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_delete_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=active_company_id)
            if repair.status == RepairMaintenance.STATUS_APPROVED:
                return Response({'error': 'Cannot delete an approved repair.'}, status=400)
            repair.delete()
            return Response({'success': True, 'message': 'Repair deleted.'})
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found.'}, status=404)


class RepairUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=active_company_id)
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found.'}, status=404)

        if repair.status == RepairMaintenance.STATUS_APPROVED:
            return Response({'error': 'Approved repairs cannot be edited.'}, status=400)

        # If already submitted to bank, clear the bank submission so it goes back to draft
        if repair.status == RepairMaintenance.STATUS_SUBMITTED:
            try:
                repair.bank.delete()
            except RepairBankSettlement.DoesNotExist:
                pass

        data  = request.data
        files = request.FILES

        vehicle_id = data.get('vehicle_id')
        if vehicle_id:
            try:
                repair.vehicle = Vehicle.objects.get(id=vehicle_id, company_id=active_company_id)
            except Vehicle.DoesNotExist:
                pass
        repair.notes = data.get('notes', repair.notes)

        # KM fields — mandatory on update
        starting_km_raw  = data.get('starting_km', '').strip()
        ending_km_raw    = data.get('ending_km', '').strip()
        starting_km_file = files.get('starting_km_attachment')
        ending_km_file   = files.get('ending_km_attachment')

        if not starting_km_raw:
            return Response({'error': 'Starting KM is required.'}, status=400)
        if not starting_km_file and not repair.starting_km_attachment:
            return Response({'error': 'Starting KM attachment is required.'}, status=400)
        if not ending_km_raw:
            return Response({'error': 'Ending KM is required.'}, status=400)
        if not ending_km_file and not repair.ending_km_attachment:
            return Response({'error': 'Ending KM attachment is required.'}, status=400)

        try:
            repair.starting_km = int(starting_km_raw)
            repair.ending_km   = int(ending_km_raw)
        except ValueError:
            return Response({'error': 'KM values must be whole numbers.'}, status=400)

        if starting_km_file:
            repair.starting_km_attachment = starting_km_file
        if ending_km_file:
            repair.ending_km_attachment = ending_km_file

        # Rebuild items
        items = []
        idx = 0
        while True:
            name = data.get(f'item_name_{idx}')
            if not name:
                break
            try:
                amount = Decimal(str(data.get(f'item_amount_{idx}', '0') or '0'))
            except Exception:
                amount = Decimal('0')
            items.append({
                'name': name,
                'description': data.get(f'item_description_{idx}', ''),
                'amount': amount,
                'file': files.get(f'item_attachment_{idx}'),
            })
            idx += 1

        if not items:
            return Response({'error': 'At least one repair item is required.'}, status=400)

        repair.total_amount = sum(i['amount'] for i in items)
        repair.status = RepairMaintenance.STATUS_DRAFT
        repair.save()

        repair.items.all().delete()
        for item in items:
            ri = RepairItem(repair=repair, name=item['name'],
                            description=item['description'], amount=item['amount'])
            if item['file']:
                ri.attachment = item['file']
            ri.save()

        return Response({'success': True, 'message': 'Repair updated.'})


# =============================================
# SETTLEMENT DELETE APIs
# =============================================

class TripSettlementDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_delete_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=active_company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)
        try:
            settlement = booking.settlement
        except TripSettlement.DoesNotExist:
            return Response({'error': 'No settlement found for this booking'}, status=404)
        settlement.delete()
        return Response({'success': True, 'message': f'Settlement for {booking.booking_number} deleted.'})


class BankSettlementDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_delete_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            bank = BankSettlement.objects.get(
                pk=pk, settlement__booking__company_id=active_company_id
            )
        except BankSettlement.DoesNotExist:
            return Response({'error': 'Bank settlement not found'}, status=404)
        bank.delete()
        return Response({'success': True, 'message': 'Bank settlement deleted.'})


# =============================================
# REPORT SUMMARY API  (totals from all time, no date filter)
# =============================================

class HolidayReportSummaryAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'bank_total': '0.00', 'repair_total': '0.00', 'nav_settlement_pending': 0, 'nav_bank_pending': 0})

        from django.db.models import Sum

        auto_complete_bookings(active_company_id)

        bank_total = BankSettlement.objects.filter(
            settlement__booking__company_id=active_company_id,
            status=BankSettlement.STATUS_APPROVED,
        ).aggregate(t=Sum('settlement__net_balance'))['t'] or 0

        repair_total = RepairMaintenance.objects.filter(
            company_id=active_company_id,
            bank__status=RepairBankSettlement.STATUS_APPROVED,
        ).aggregate(t=Sum('total_amount'))['t'] or 0

        # Completed trips that have no settlement yet
        completed_ids = set(HolidayBooking.objects.filter(
            company_id=active_company_id, status='COMPLETED',
        ).values_list('id', flat=True))
        settled_ids = set(TripSettlement.objects.filter(
            booking_id__in=completed_ids
        ).values_list('booking_id', flat=True))
        nav_settlement_pending = len(completed_ids - settled_ids)

        from django.db.models import Q

        # Order form settlements: no bank doc yet OR pending approval
        order_bank_pending = TripSettlement.objects.filter(
            booking__company_id=active_company_id,
        ).filter(
            Q(bank__isnull=True) | Q(bank__status=BankSettlement.STATUS_PENDING)
        ).count()

        # Repair entries: no bank submission yet OR pending approval
        repair_bank_pending = RepairMaintenance.objects.filter(
            company_id=active_company_id,
        ).filter(
            Q(bank__isnull=True) | Q(bank__status=RepairBankSettlement.STATUS_PENDING)
        ).count()

        return Response({
            'bank_total':               str(Decimal(str(bank_total)).quantize(Decimal('0.01'))),
            'repair_total':             str(Decimal(str(repair_total)).quantize(Decimal('0.01'))),
            'nav_settlement_pending':   nav_settlement_pending,
            'nav_bank_pending':         order_bank_pending + repair_bank_pending,
            'nav_bank_order_pending':   order_bank_pending,
            'nav_bank_repair_pending':  repair_bank_pending,
        })


# =============================================
# QUICK STAT LIST API
# =============================================

class HolidayQuickListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'bookings': []})

        from django.utils import timezone
        import datetime

        stat_type = request.GET.get('type', '')
        now       = timezone.localtime(timezone.now())
        today     = now.date()

        qs = HolidayBooking.objects.filter(
            company_id=active_company_id,
        ).select_related('booked_vehicle').order_by('trip_date')

        if stat_type == 'enquiry':
            qs = qs.filter(status='PENDING')

        elif stat_type == 'upcoming':
            from django.db.models import Q
            qs = qs.filter(
                trip_date__gte=today,
                status='CONFIRMED',
            ).filter(
                Q(return_date__isnull=True) | Q(return_date__gte=today)
            )

        elif stat_type == 'completed':
            auto_complete_bookings(active_company_id)
            qs = qs.filter(status='COMPLETED')

        elif stat_type == 'this-month':
            try:
                month = int(request.GET.get('month', today.month))
                year  = int(request.GET.get('year',  today.year))
            except (ValueError, TypeError):
                month, year = today.month, today.year
            qs = qs.filter(
                trip_date__month=month,
                trip_date__year=year,
                status__in=['PENDING', 'CONFIRMED'],
            )

        else:
            qs = qs.none()

        bookings = [{
            'id':             b.id,
            'booking_number': b.booking_number,
            'trip_date':      b.trip_date.strftime('%d %b %Y'),
            'return_date':    b.return_date.strftime('%d %b %Y') if b.return_date else '—',
            'destination':    b.destination,
            'booked_by':      b.booked_by,
            'vehicle':        str(b.booked_vehicle) if b.booked_vehicle else '—',
            'status':         b.status,
        } for b in qs]

        return Response({'bookings': bookings})


# =============================================
# REPORT APIs
# =============================================

class HolidayBankReportAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'entries': []})

        from_date = request.GET.get('from_date')
        to_date   = request.GET.get('to_date')

        qs = BankSettlement.objects.filter(
            settlement__booking__company_id=active_company_id,
            status=BankSettlement.STATUS_APPROVED,
        ).select_related(
            'settlement__booking',
            'settlement__booking__booked_vehicle',
            'approved_by',
        )
        if from_date:
            qs = qs.filter(approved_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(approved_at__date__lte=to_date)
        qs = qs.order_by('approved_at')

        entries = []
        for i, bank in enumerate(qs, 1):
            s = bank.settlement
            b = s.booking
            entries.append({
                'sl':            i,
                'booking_number': b.booking_number,
                'booked_by':     b.booked_by,
                'contact_number': b.contact_number,
                'trip_date':     b.trip_date.strftime('%Y-%m-%d'),
                'return_date':   b.return_date.strftime('%Y-%m-%d') if b.return_date else '—',
                'destination':   b.destination,
                'vehicle':       str(b.booked_vehicle) if b.booked_vehicle else '—',
                'total_amount':  str(b.total_amount),
                'net_balance':   str(s.net_balance),
                'approved_by':   (bank.approved_by.get_full_name() or bank.approved_by.username) if bank.approved_by else '—',
                'approved_at':   bank.approved_at.strftime('%d %b %Y') if bank.approved_at else '—',
            })
        return Response({'entries': entries})


class RepairReportAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'entries': []})

        from_date = request.GET.get('from_date')
        to_date   = request.GET.get('to_date')

        qs = RepairMaintenance.objects.filter(
            company_id=active_company_id,
            bank__status=RepairBankSettlement.STATUS_APPROVED,
        ).select_related('vehicle', 'created_by', 'bank', 'bank__approved_by').prefetch_related('items')
        if from_date:
            qs = qs.filter(bank__approved_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(bank__approved_at__date__lte=to_date)
        qs = qs.order_by('bank__approved_at')

        entries = []
        for i, r in enumerate(qs, 1):
            try:
                bank = r.bank
                bank_status      = bank.status
                bank_approved_by = (bank.approved_by.get_full_name() or bank.approved_by.username) if bank.approved_by else '—'
                bank_approved_at = bank.approved_at.strftime('%d %b %Y') if bank.approved_at else '—'
            except RepairBankSettlement.DoesNotExist:
                bank_status = '—'
                bank_approved_by = '—'
                bank_approved_at = '—'

            entries.append({
                'sl':              i,
                'repair_number':   r.repair_number,
                'vehicle':         str(r.vehicle) if r.vehicle else '—',
                'created_at':      r.created_at.strftime('%d %b %Y'),
                'items':           [{'name': it.name, 'amount': str(it.amount)} for it in r.items.all()],
                'total_amount':    str(r.total_amount),
                'status':          r.status,
                'bank_status':     bank_status,
                'bank_approved_by': bank_approved_by,
                'bank_approved_at': bank_approved_at,
                'notes':           r.notes or '',
            })
        return Response({'entries': entries})
