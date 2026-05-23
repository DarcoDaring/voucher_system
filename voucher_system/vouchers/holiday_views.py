from django.shortcuts import redirect
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import HolidayBooking, Company, UserPermission
from .views import check_user_permission
from decimal import Decimal


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
            booking = HolidayBooking.objects.create(
                company=company,
                trip_date=data['trip_date'],
                destination=data['destination'],
                departure_location=data['departure_location'],
                departure_time=data['departure_time'],
                return_time=data.get('return_time') or None,
                bus_type=data.get('bus_type', 'STANDARD'),
                no_of_passengers=int(data['no_of_passengers']),
                booked_by=data['booked_by'],
                contact_number=data['contact_number'],
                fare_per_person=Decimal(data.get('fare_per_person', 0)),
                advance_amount=Decimal(data.get('advance_amount', 0)) if data.get('advance_amount') else None,
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
        ).select_related('created_by')

        data = [{
            'id': b.id,
            'booking_number': b.booking_number,
            'destination': b.destination,
            'departure_location': b.departure_location,
            'departure_time': b.departure_time.strftime('%H:%M'),
            'return_time': b.return_time.strftime('%H:%M') if b.return_time else None,
            'bus_type': b.get_bus_type_display(),
            'no_of_passengers': b.no_of_passengers,
            'booked_by': b.booked_by,
            'contact_number': b.contact_number,
            'total_amount': str(b.total_amount),
            'status': b.status,
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


class HolidayConfirmAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=active_company_id)
            new_status = request.data.get('status', 'CONFIRMED')
            booking.status = new_status
            booking.save(update_fields=['status'])
            return Response({'success': True, 'status': booking.status})
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)
