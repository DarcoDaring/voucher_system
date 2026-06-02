from django.shortcuts import redirect
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import HolidayBooking, Company, UserPermission, Vehicle, PaymentType, TripSettlement, TripSettlementCharge, BankSettlement, HolidayBankApprover
from .views import check_user_permission
from decimal import Decimal


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
        context['is_superuser']       = self.request.user.is_superuser
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
            context['can_edit'] = True
        else:
            perms = (
                UserPermission.get_or_create_for_user(
                    self.request.user,
                    Company.objects.get(id=active_company_id)
                ) if active_company_id else None
            )
            context['can_edit'] = bool(perms and perms.can_edit_holiday)
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

        bookings = HolidayBooking.objects.filter(
            company_id=active_company_id,
            status__in=['PENDING', 'CONFIRMED']
        ).values('trip_date', 'booking_number', 'destination', 'status', 'id')

        events = []
        for b in bookings:
            color = '#0d6efd' if b['status'] == 'CONFIRMED' else '#ffc107'
            events.append({
                'id': b['id'],
                'title': f"{b['booking_number']} – {b['destination']}",
                'start': b['trip_date'].isoformat(),
                'color': color,
                'url': f"/holidays/{b['id']}/",
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

        data = request.data
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

        from django.utils import timezone
        import datetime

        now = timezone.localtime(timezone.now())

        bookings = HolidayBooking.objects.filter(
            company_id=active_company_id,
            return_date__isnull=False,
            return_time__isnull=False,
        ).select_related('booked_vehicle', 'created_by').order_by('-return_date', '-return_time')

        # build settlement lookup once
        settlement_map = {
            s.booking_id: s.id
            for s in TripSettlement.objects.filter(booking__company_id=active_company_id)
        }

        completed = []
        for b in bookings:
            return_dt = timezone.make_aware(
                datetime.datetime.combine(b.return_date, b.return_time)
            )
            if now >= return_dt:
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

        from django.utils import timezone
        import datetime

        now = timezone.localtime(timezone.now())
        bookings = HolidayBooking.objects.filter(
            company_id=active_company_id,
            return_date__isnull=False,
            return_time__isnull=False,
        )
        count = sum(
            1 for b in bookings
            if now >= timezone.make_aware(datetime.datetime.combine(b.return_date, b.return_time))
        )
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
        context['is_superuser'] = self.request.user.is_superuser
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
