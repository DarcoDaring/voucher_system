from django.shortcuts import redirect
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import FunctionBooking, Company, CompanyMembership, UserPermission
from .views import check_user_permission
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.utils import timezone


def is_function_completed_check(function_date, time_to):
    import datetime as dt
    now = timezone.localtime(timezone.now())
    function_end_datetime = timezone.make_aware(
        dt.datetime.combine(function_date, time_to)
    )
    return now >= function_end_datetime


class FunctionDetailsView(LoginRequiredMixin, TemplateView):
    template_name = 'vouchers/function.html'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        if active_company_id:
            try:
                co = Company.objects.get(id=active_company_id)
                if not co.enable_functions:
                    messages.error(request, 'Functions module is not enabled for this company.')
                    return redirect('home')
            except Company.DoesNotExist:
                pass
        has_perm, error = check_user_permission(request.user, 'can_view_function_list', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['can_create_function'] = user.is_authenticated
        context['is_admin_staff'] = user.is_authenticated and (
            user.groups.filter(name='Admin Staff').exists() or user.is_superuser
        )
        return context


class FunctionGenerateNumberAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'function_number': 'FN0001'})

        try:
            company = Company.objects.get(id=active_company_id)
            last_function = FunctionBooking.objects.filter(company=company).order_by('-id').first()
            if last_function and last_function.function_number.startswith('FN'):
                num = int(last_function.function_number[2:]) + 1
                function_number = f'FN{num:04d}'
            else:
                function_number = 'FN0001'
        except Company.DoesNotExist:
            function_number = 'FN0001'

        return Response({'function_number': function_number})


class FunctionCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            import json

            active_company_id = request.session.get('active_company_id')
            if not active_company_id:
                return Response({'error': 'No active company selected'}, status=400)

            has_perm, error = check_user_permission(request.user, 'can_create_function', active_company_id)
            if not has_perm:
                return Response({'error': error}, status=403)

            try:
                company = Company.objects.get(id=active_company_id)
            except Company.DoesNotExist:
                return Response({'error': 'Invalid company'}, status=404)

            function_date = request.data.get('function_date')
            time_from = request.data.get('time_from')
            time_to = request.data.get('time_to')
            function_name = request.data.get('function_name', '').strip()
            booked_by = request.data.get('booked_by', '').strip()

            contact_numbers = json.loads(request.data.get('contact_numbers', '[]'))
            if not contact_numbers:
                return Response({'error': 'At least one contact number is required'}, status=400)

            address = request.data.get('address', '').strip()
            menu_items = json.loads(request.data.get('menu_items', '{}'))

            location = request.data.get('location', '').strip()
            if not location:
                return Response({'error': 'Location is required'}, status=400)

            if location not in ['Banquet', 'Restaurant', 'Family Room', 'Outdoor']:
                return Response({'error': 'Invalid location selected'}, status=400)

            no_of_pax = request.data.get('no_of_pax')
            rate_per_pax = request.data.get('rate_per_pax', 0)
            gst_option = request.data.get('gst_option', 'INCLUDING')
            hall_rent = request.data.get('hall_rent', 0) or 0
            extra_charges = json.loads(request.data.get('extra_charges', '[]'))
            special_instructions = request.data.get('special_instructions', '').strip()

            if not all([function_date, time_from, time_to, function_name, address, no_of_pax, rate_per_pax]):
                return Response({'error': 'All required fields must be filled'}, status=400)

            function = FunctionBooking.objects.create(
                company=company,
                function_date=function_date,
                time_from=time_from,
                time_to=time_to,
                function_name=function_name,
                booked_by=booked_by,
                contact_numbers=contact_numbers,
                address=address,
                menu_items=menu_items,
                location=location,
                no_of_pax=no_of_pax,
                rate_per_pax=rate_per_pax,
                gst_option=gst_option,
                hall_rent=hall_rent,
                extra_charges=extra_charges,
                special_instructions=special_instructions,
                created_by=request.user
            )

            return Response({
                'success': True,
                'function': {
                    'id': function.id,
                    'function_number': function.function_number,
                    'booked_by': function.booked_by,
                    'total_amount': str(function.total_amount)
                }
            }, status=201)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class FunctionBookedDatesAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'booked_dates': []})

        booked_dates = FunctionBooking.objects.filter(
            company_id=active_company_id
        ).values_list('function_date', flat=True).distinct()

        dates = [d.strftime('%Y-%m-%d') for d in booked_dates]
        return Response({'booked_dates': dates})


class FunctionListByDateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.GET.get('date')
        if not date_str:
            return Response({'error': 'Date parameter required'}, status=400)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'functions': []})

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()

            functions = FunctionBooking.objects.filter(
                company_id=active_company_id,
                function_date=date
            ).order_by('time_from')

            data = [{
                'id': f.id,
                'function_number': f.function_number,
                'function_name': f.function_name,
                'function_date': f.function_date.strftime('%Y-%m-%d'),
                'time_from': f.time_from.strftime('%H:%M'),
                'time_to': f.time_to.strftime('%H:%M'),
                'booked_by': f.booked_by,
                'contact_numbers': f.contact_numbers,
                'no_of_pax': f.no_of_pax,
                'total_amount': str(f.total_amount),
                'status': f.status,
                'advance_amount': str(f.advance_amount) if f.advance_amount else None,
                'is_completed': is_function_completed_check(f.function_date, f.time_to)
            } for f in functions]

            return Response({'functions': data})
        except ValueError:
            return Response({'error': 'Invalid date format'}, status=400)


class FunctionDetailView(LoginRequiredMixin, DetailView):
    model = FunctionBooking
    template_name = 'vouchers/function_detail.html'
    context_object_name = 'function'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_view_function_detail', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        active_company_id = self.request.session.get('active_company_id')
        if not active_company_id:
            return FunctionBooking.objects.none()
        return FunctionBooking.objects.filter(company_id=active_company_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_admin_staff'] = user.is_authenticated and (
            user.groups.filter(name='Admin Staff').exists() or user.is_superuser
        )
        return context


class FunctionDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        has_perm, error = check_user_permission(request.user, 'can_delete_function', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            function = FunctionBooking.objects.get(pk=pk, company_id=active_company_id)
            function_number = function.function_number
            function.delete()
            return Response({
                'success': True,
                'message': f'Function {function_number} deleted successfully'
            })
        except FunctionBooking.DoesNotExist:
            return Response({'error': 'Function not found or does not belong to active company'}, status=404)


class FunctionConfirmAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        has_perm, error = check_user_permission(request.user, 'can_edit_function', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            function = FunctionBooking.objects.get(pk=pk, company_id=active_company_id)
        except FunctionBooking.DoesNotExist:
            return Response({'error': 'Function not found'}, status=404)

        try:
            if function.status == 'CONFIRMED':
                return Response({'error': 'Function is already confirmed'}, status=400)

            advance_amount = request.data.get('advance_amount')
            due_amount = request.data.get('due_amount')
            food_pickup_time_str = request.data.get('food_pickup_time')
            food_service_time_str = request.data.get('food_service_time')

            if not advance_amount:
                return Response({'error': 'Advance amount is required'}, status=400)

            try:
                advance_amount = Decimal(str(advance_amount))
                due_amount = Decimal(str(due_amount))

                if advance_amount < 0:
                    return Response({'error': 'Advance amount must be positive'}, status=400)

                if advance_amount > function.total_amount:
                    return Response({'error': 'Advance amount cannot exceed total amount'}, status=400)

                calculated_due = function.total_amount - advance_amount
                if abs(calculated_due - due_amount) > Decimal('0.01'):
                    return Response({'error': 'Due amount calculation mismatch'}, status=400)

            except (InvalidOperation, ValueError):
                return Response({'error': 'Invalid amount format'}, status=400)

            def parse_time(time_str):
                if not time_str or str(time_str).strip() in ('', 'null', 'None'):
                    return None
                try:
                    return datetime.strptime(str(time_str).strip(), '%H:%M').time()
                except ValueError:
                    return None

            function.food_pickup_time = parse_time(food_pickup_time_str)
            function.food_service_time = parse_time(food_service_time_str)
            function.status = 'CONFIRMED'
            function.advance_amount = advance_amount
            function.due_amount = due_amount
            function.confirmed_by = request.user
            function.confirmed_at = timezone.now()
            function.save()

            return Response({
                'success': True,
                'message': f'Function {function.function_number} confirmed successfully!',
                'function': {
                    'id': function.id,
                    'function_number': function.function_number,
                    'status': function.status,
                    'location': function.location,
                    'total_amount': str(function.total_amount),
                    'advance_amount': str(function.advance_amount),
                    'due_amount': str(function.due_amount),
                    'food_pickup_time': function.food_pickup_time.strftime('%H:%M') if function.food_pickup_time else None,
                    'food_service_time': function.food_service_time.strftime('%H:%M') if function.food_service_time else None,
                    'confirmed_by': function.confirmed_by.username,
                    'confirmed_at': function.confirmed_at.strftime('%d %b %Y, %H:%M')
                }
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class FunctionUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        has_perm, error = check_user_permission(request.user, 'can_edit_function', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            import json
            function = FunctionBooking.objects.get(pk=pk)

            function.function_date = request.data.get('function_date', function.function_date)
            function.time_from = request.data.get('time_from', function.time_from)
            function.time_to = request.data.get('time_to', function.time_to)
            function.function_name = request.data.get('function_name', function.function_name).strip()
            function.booked_by = request.data.get('booked_by', function.booked_by).strip()

            contact_numbers = json.loads(request.data.get('contact_numbers', '[]'))
            if contact_numbers:
                function.contact_numbers = contact_numbers

            function.address = request.data.get('address', function.address).strip()
            menu_items = json.loads(request.data.get('menu_items', '{}'))
            function.menu_items = menu_items

            location = request.data.get('location')
            if location:
                if location not in ['Banquet', 'Restaurant', 'Family Room', 'Outdoor']:
                    return Response({'error': 'Invalid location selected'}, status=400)
                function.location = location

            function.no_of_pax = request.data.get('no_of_pax', function.no_of_pax)
            function.rate_per_pax = request.data.get('rate_per_pax', function.rate_per_pax)
            function.gst_option = request.data.get('gst_option', function.gst_option)
            function.hall_rent = request.data.get('hall_rent', function.hall_rent) or 0

            extra_charges = json.loads(request.data.get('extra_charges', '[]'))
            function.extra_charges = extra_charges

            special_instructions = request.data.get('special_instructions', '').strip()
            function.special_instructions = special_instructions

            function.save()

            return Response({
                'success': True,
                'message': f'Function {function.function_number} updated successfully',
                'function': {
                    'id': function.id,
                    'function_number': function.function_number,
                    'total_amount': str(function.total_amount)
                }
            })

        except FunctionBooking.DoesNotExist:
            return Response({'error': 'Function not found'}, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class FunctionPrintView(LoginRequiredMixin, DetailView):
    model = FunctionBooking
    template_name = 'vouchers/function_print.html'
    context_object_name = 'function'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_print_function', active_company_id)
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
        else:
            context['company'] = None
        return context


class FunctionUpcomingEventsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'success': True, 'functions': [], 'count': 0})

        now = timezone.localtime(timezone.now())
        today_date = now.date()
        current_time = now.time()

        functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            status='CONFIRMED',
            function_date__gte=today_date
        ).order_by('function_date', 'time_from')

        upcoming_functions = []
        for f in functions:
            if f.function_date > today_date:
                upcoming_functions.append(f)
            elif f.function_date == today_date:
                if f.time_to > current_time:
                    upcoming_functions.append(f)

        data = [{
            'id': f.id,
            'function_number': f.function_number,
            'function_name': f.function_name,
            'function_date': f.function_date.strftime('%Y-%m-%d'),
            'formatted_date': f.function_date.strftime('%d %b %Y'),
            'time_from': f.time_from.strftime('%H:%M'),
            'time_to': f.time_to.strftime('%H:%M'),
            'booked_by': f.booked_by,
            'location': f.location,
            'no_of_pax': f.no_of_pax,
            'total_amount': str(f.total_amount),
            'advance_amount': str(f.advance_amount) if f.advance_amount else None,
            'due_amount': str(f.due_amount) if f.due_amount else None,
        } for f in upcoming_functions]

        return Response({'success': True, 'functions': data, 'count': len(data)})


class FunctionPendingByMonthAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'success': True, 'functions': [], 'count': 0})

        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month + 1, 1).date()

        pending_functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            function_date__gte=start_date,
            function_date__lt=end_date,
            status='PENDING'
        ).order_by('function_date', 'time_from')

        data = [{
            'id': f.id,
            'function_number': f.function_number,
            'function_name': f.function_name,
            'function_date': f.function_date.strftime('%Y-%m-%d'),
            'formatted_date': f.function_date.strftime('%d %b %Y'),
            'time_from': f.time_from.strftime('%H:%M'),
            'time_to': f.time_to.strftime('%H:%M'),
            'booked_by': f.booked_by,
            'location': f.location,
            'no_of_pax': f.no_of_pax,
            'total_amount': str(f.total_amount),
        } for f in pending_functions]

        return Response({'success': True, 'functions': data, 'count': len(data)})


class FunctionUpcomingCountAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'count': 0})

        now = timezone.localtime(timezone.now())
        today_date = now.date()
        current_time = now.time()

        functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            status='CONFIRMED',
            function_date__gte=today_date
        )

        count = 0
        for f in functions:
            if f.function_date > today_date:
                count += 1
            elif f.function_date == today_date and f.time_to > current_time:
                count += 1

        return Response({'count': count})


class FunctionCompletedCountAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'count': 0})

        now = timezone.localtime(timezone.now())
        today_date = now.date()
        current_time = now.time()

        functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            status='CONFIRMED',
            function_date__lte=today_date
        )

        count = 0
        for f in functions:
            if f.function_date < today_date:
                count += 1
            elif f.function_date == today_date and f.time_to <= current_time:
                count += 1

        return Response({'count': count})


class FunctionCompletedAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'success': True, 'functions': []})

        now = timezone.localtime(timezone.now())
        today_date = now.date()
        current_time = now.time()

        functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            status='CONFIRMED',
            function_date__lte=today_date
        ).order_by('-function_date', 'time_from')

        completed_functions = []
        for f in functions:
            if f.function_date < today_date:
                completed_functions.append(f)
            elif f.function_date == today_date and f.time_to <= current_time:
                completed_functions.append(f)

        data = [{
            'id': f.id,
            'function_number': f.function_number,
            'function_name': f.function_name,
            'function_date': f.function_date.strftime('%Y-%m-%d'),
            'formatted_date': f.function_date.strftime('%d %b %Y'),
            'time_from': f.time_from.strftime('%H:%M'),
            'time_to': f.time_to.strftime('%H:%M'),
            'booked_by': f.booked_by,
            'location': f.location,
            'no_of_pax': f.no_of_pax,
            'total_amount': str(f.total_amount),
        } for f in completed_functions]

        return Response({'success': True, 'functions': data})


class FunctionListByMonthAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date_str = request.GET.get('start')
        end_date_str = request.GET.get('end')

        if not start_date_str or not end_date_str:
            return Response({'error': 'start and end date parameters required'}, status=400)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'functions': []})

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            functions = FunctionBooking.objects.filter(
                company_id=active_company_id,
                function_date__gte=start_date,
                function_date__lte=end_date
            ).order_by('function_date', 'time_from')

            data = [{
                'id': f.id,
                'function_number': f.function_number,
                'function_name': f.function_name,
                'function_date': f.function_date.strftime('%Y-%m-%d'),
                'status': f.status,
            } for f in functions]

            return Response({'success': True, 'functions': data})

        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class FunctionUpdateDetailsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not (request.user.is_superuser or request.user.groups.filter(name='Admin Staff').exists()):
            return Response({'error': 'Permission denied'}, status=403)

        try:
            function = FunctionBooking.objects.get(pk=pk)

            food_pickup_time_str = request.data.get('food_pickup_time')
            food_service_time_str = request.data.get('food_service_time')

            def parse_time(time_str):
                if not time_str or time_str in ('', None, 'null'):
                    return None
                try:
                    return datetime.strptime(time_str, '%H:%M').time()
                except ValueError:
                    return None

            function.food_pickup_time = parse_time(food_pickup_time_str)
            function.food_service_time = parse_time(food_service_time_str)

            if 'special_instructions' in request.data:
                special_instructions = request.data.get('special_instructions', '').strip()
                function.special_instructions = special_instructions if special_instructions else None

            function.save()

            return Response({
                'success': True,
                'message': 'Food times updated successfully!',
                'function': {
                    'id': function.id,
                    'food_pickup_time': function.food_pickup_time.strftime('%H:%M') if function.food_pickup_time else None,
                    'food_service_time': function.food_service_time.strftime('%H:%M') if function.food_service_time else None,
                    'special_instructions': function.special_instructions
                }
            })

        except FunctionBooking.DoesNotExist:
            return Response({'error': 'Function not found'}, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': 'An error occurred while saving details'}, status=500)


class FunctionTimeConflictCheckAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        function_date = request.data.get('function_date')
        time_from = request.data.get('time_from')
        time_to = request.data.get('time_to')
        function_id = request.data.get('function_id')

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        if not all([function_date, time_from, time_to]):
            return Response({'error': 'Date and times are required'}, status=400)

        try:
            check_date = datetime.strptime(function_date, '%Y-%m-%d').date()
            check_time_from = datetime.strptime(time_from, '%H:%M').time()
            check_time_to = datetime.strptime(time_to, '%H:%M').time()

            existing_functions = FunctionBooking.objects.filter(
                company_id=active_company_id,
                function_date=check_date
            )

            if function_id:
                existing_functions = existing_functions.exclude(id=function_id)

            conflicts = []
            for func in existing_functions:
                if (check_time_from < func.time_to) and (check_time_to > func.time_from):
                    conflicts.append({
                        'function_number': func.function_number,
                        'function_name': func.function_name,
                        'time_from': func.time_from.strftime('%H:%M'),
                        'time_to': func.time_to.strftime('%H:%M'),
                        'booked_by': func.booked_by,
                        'location': func.location,
                        'status': func.status
                    })

            if conflicts:
                return Response({
                    'has_conflict': True,
                    'conflicts': conflicts,
                    'message': f"Found {len(conflicts)} function(s) with overlapping time"
                })
            else:
                return Response({
                    'has_conflict': False,
                    'message': 'No time conflicts found'
                })

        except ValueError as e:
            return Response({'error': f'Invalid date/time format: {str(e)}'}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)
