# vouchers/mobile_holidays_api.py
# Mobile-only token-authenticated endpoints for the Holidays module.

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.utils import timezone
import re

from .models import (
    HolidayBooking, Company, UserPermission, Vehicle, PaymentType,
    TripSettlement, TripSettlementCharge, BankSettlement,
    HolidayBankApprover, RepairMaintenance, RepairItem, RepairBankSettlement,
    CompanyMembership,
)
from .holiday_views import auto_complete_bookings, auto_delete_expired_pending
from .views import check_user_permission


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _has_company_access(user, company_id):
    if not company_id:
        return False
    if user.is_superuser:
        return Company.objects.filter(id=company_id, is_active=True).exists()
    return CompanyMembership.objects.filter(
        user=user, company_id=company_id, is_active=True, company__is_active=True
    ).exists()


def _get_permissions_dict(user, company_id):
    if user.is_superuser:
        return {
            'can_create_holiday': True, 'can_edit_holiday': True,
            'can_delete_holiday': True, 'can_view_holiday_list': True,
            'can_view_holiday_detail': True, 'is_approver': True,
        }
    try:
        company = Company.objects.get(id=company_id)
        perms = UserPermission.get_or_create_for_user(user, company)
        is_approver = HolidayBankApprover.objects.filter(
            company_id=company_id, user=user, is_active=True
        ).exists()
        return {
            'can_create_holiday': perms.can_create_holiday,
            'can_edit_holiday': perms.can_edit_holiday,
            'can_delete_holiday': perms.can_delete_holiday,
            'can_view_holiday_list': perms.can_view_holiday_list,
            'can_view_holiday_detail': perms.can_view_holiday_detail,
            'is_approver': is_approver,
        }
    except Company.DoesNotExist:
        return {k: False for k in [
            'can_create_holiday', 'can_edit_holiday', 'can_delete_holiday',
            'can_view_holiday_list', 'can_view_holiday_detail', 'is_approver'
        ]}


# ─────────────────────────────────────────────────────────────────
# 1. PERMISSIONS
# ─────────────────────────────────────────────────────────────────

class MobileHolidayPermissionsAPI(APIView):
    """GET /api/mobile/holidays/permissions/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)
        return Response(_get_permissions_dict(request.user, company_id))


# ─────────────────────────────────────────────────────────────────
# 2. DASHBOARD STATS
# ─────────────────────────────────────────────────────────────────

class MobileHolidayStatsAPI(APIView):
    """GET /api/mobile/holidays/stats/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        auto_complete_bookings(company_id)

        enquiry_count = HolidayBooking.objects.filter(
            company_id=company_id, status='PENDING'
        ).count()
        upcoming_count = HolidayBooking.objects.filter(
            company_id=company_id, status='CONFIRMED'
        ).count()
        completed_count = HolidayBooking.objects.filter(
            company_id=company_id, status='COMPLETED'
        ).count()

        # Completed trips without settlement
        settled_booking_ids = TripSettlement.objects.filter(
            booking__company_id=company_id
        ).values_list('booking_id', flat=True)
        settlement_pending = HolidayBooking.objects.filter(
            company_id=company_id, status='COMPLETED'
        ).exclude(id__in=settled_booking_ids).count()

        bank_pending = BankSettlement.objects.filter(
            settlement__booking__company_id=company_id,
            status=BankSettlement.STATUS_PENDING,
        ).count()

        repair_active = RepairMaintenance.objects.filter(
            company_id=company_id
        ).exclude(status=RepairMaintenance.STATUS_APPROVED).count()

        return Response({
            'enquiry_count': enquiry_count,
            'upcoming_count': upcoming_count,
            'completed_count': completed_count,
            'settlement_pending': settlement_pending,
            'bank_pending': bank_pending,
            'repair_active': repair_active,
        })


# ─────────────────────────────────────────────────────────────────
# 3. HOLIDAY BOOKING LIST
# ─────────────────────────────────────────────────────────────────

class MobileHolidayListAPI(APIView):
    """GET /api/mobile/holidays/?company_id=<id>&status=PENDING|CONFIRMED|COMPLETED"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        auto_complete_bookings(company_id)
        auto_delete_expired_pending(company_id)

        qs = HolidayBooking.objects.filter(
            company_id=company_id
        ).select_related('booked_vehicle', 'created_by').order_by('-trip_date', '-id')

        status_filter = request.query_params.get('status', '')
        if status_filter:
            qs = qs.filter(status=status_filter)

        data = [{
            'id': b.id,
            'booking_number': b.booking_number,
            'trip_date': b.trip_date.isoformat(),
            'return_date': b.return_date.isoformat() if b.return_date else None,
            'destination': b.destination,
            'departure_location': b.departure_location,
            'departure_time': b.departure_time.strftime('%H:%M') if b.departure_time else None,
            'return_time': b.return_time.strftime('%H:%M') if b.return_time else None,
            'booked_by': b.booked_by,
            'contact_number': b.contact_number,
            'status': b.status,
            'total_amount': str(b.total_amount or 0),
            'booked_vehicle': str(b.booked_vehicle) if b.booked_vehicle else None,
            'no_of_passengers': b.no_of_passengers,
            'ac_type': b.ac_type,
        } for b in qs]

        return Response({'bookings': data, 'count': len(data)})


# ─────────────────────────────────────────────────────────────────
# 4. CREATE HOLIDAY BOOKING
# ─────────────────────────────────────────────────────────────────

class MobileHolidayCreateAPI(APIView):
    """POST /api/mobile/holidays/create/"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        has_perm, error = check_user_permission(request.user, 'can_create_holiday', company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=400)

        data = request.data
        contact = str(data.get('contact_number', ''))
        if not re.match(r'^\d{10}$', contact):
            return Response({'error': 'Contact number must be exactly 10 digits.'}, status=400)
        second = data.get('second_contact_number')
        if second and not re.match(r'^\d{10}$', str(second)):
            return Response({'error': 'Second contact must be exactly 10 digits.'}, status=400)

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
                second_contact_number=second or None,
                departure_location=data['departure_location'],
                destination=data['destination'],
                departure_time=data['departure_time'],
                return_date=data.get('return_date') or None,
                return_time=data.get('return_time') or None,
                no_of_passengers=int(data.get('no_of_passengers', 1)),
                booked_vehicle=booked_vehicle,
                ac_type=data.get('ac_type', 'NON_AC'),
                payment_type_label=data.get('payment_type_label', ''),
                total_rent=Decimal(str(data.get('total_rent', 0) or 0)),
                service_charge=Decimal(str(data.get('service_charge', 0) or 0)),
                advance_amount=Decimal(str(data.get('advance_amount', 0) or 0)),
                max_km=int(data['max_km']) if data.get('max_km') else None,
                extra_km_charge=Decimal(str(data['extra_km_charge'])) if data.get('extra_km_charge') else None,
                special_instructions=data.get('special_instructions', ''),
                status='PENDING',
                created_by=request.user,
            )
            return Response({
                'success': True,
                'booking_number': booking.booking_number,
                'id': booking.id,
                'message': f'Booking {booking.booking_number} created successfully!',
            }, status=201)
        except KeyError as e:
            return Response({'error': f'Missing required field: {e}'}, status=400)
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────
# 5. HOLIDAY DETAIL
# ─────────────────────────────────────────────────────────────────

class MobileHolidayDetailAPI(APIView):
    """GET /api/mobile/holidays/<pk>/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        try:
            b = HolidayBooking.objects.select_related(
                'booked_vehicle', 'created_by'
            ).get(pk=pk, company_id=company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        is_bank_approved = False
        has_settlement = False
        settlement_id = None
        try:
            s = b.settlement
            has_settlement = True
            settlement_id = s.id
            is_bank_approved = s.bank.status == BankSettlement.STATUS_APPROVED
        except (TripSettlement.DoesNotExist, BankSettlement.DoesNotExist, AttributeError):
            pass

        return Response({
            'id': b.id,
            'booking_number': b.booking_number,
            'trip_date': b.trip_date.isoformat(),
            'return_date': b.return_date.isoformat() if b.return_date else None,
            'return_time': b.return_time.strftime('%H:%M') if b.return_time else None,
            'departure_time': b.departure_time.strftime('%H:%M') if b.departure_time else None,
            'booked_by': b.booked_by,
            'contact_number': b.contact_number,
            'second_contact_number': b.second_contact_number or '',
            'departure_location': b.departure_location,
            'destination': b.destination,
            'purpose_of_booking': b.purpose_of_booking or '',
            'no_of_passengers': b.no_of_passengers,
            'booked_vehicle': str(b.booked_vehicle) if b.booked_vehicle else None,
            'booked_vehicle_id': b.booked_vehicle_id,
            'ac_type': b.ac_type,
            'payment_type_label': b.payment_type_label or '',
            'total_rent': str(b.total_rent or 0),
            'service_charge': str(b.service_charge or 0),
            'advance_amount': str(b.advance_amount or 0),
            'total_amount': str(b.total_amount or 0),
            'balance_amount': str(b.balance_amount or 0),
            'max_km': b.max_km,
            'extra_km_charge': str(b.extra_km_charge) if b.extra_km_charge else None,
            'special_instructions': b.special_instructions or '',
            'status': b.status,
            'has_settlement': has_settlement,
            'settlement_id': settlement_id,
            'is_bank_approved': is_bank_approved,
            'created_by': b.created_by.get_full_name() or b.created_by.username if b.created_by else None,
            'created_at': b.created_at.strftime('%d %b %Y'),
        })


# ─────────────────────────────────────────────────────────────────
# 6. CONFIRM BOOKING
# ─────────────────────────────────────────────────────────────────

class MobileHolidayConfirmAPI(APIView):
    """POST /api/mobile/holidays/<pk>/confirm/"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        if booking.status != 'PENDING':
            return Response({'error': 'Only pending enquiries can be confirmed.'}, status=400)

        if booking.booked_vehicle_id:
            b_start = booking.trip_date
            b_end = booking.return_date or booking.trip_date
            for existing in HolidayBooking.objects.filter(
                company_id=company_id,
                booked_vehicle_id=booking.booked_vehicle_id,
                status='CONFIRMED',
            ).exclude(pk=booking.pk):
                e_start = existing.trip_date
                e_end = existing.return_date or existing.trip_date
                if b_start <= e_end and b_end >= e_start:
                    return Response({'error': (
                        f'{booking.booked_vehicle.name} is already booked for '
                        f'{existing.booking_number} '
                        f'({e_start.strftime("%d %b %Y")} – {e_end.strftime("%d %b %Y")}). '
                        f'Change the vehicle or adjust dates before confirming.'
                    )}, status=400)

        # Update advance amount if provided (balance_amount auto-recalculates via model save)
        advance_raw = request.data.get('advance_amount')
        if advance_raw not in (None, ''):
            try:
                advance = Decimal(str(advance_raw))
                if advance < 0:
                    return Response({'error': 'Advance amount cannot be negative.'}, status=400)
                if advance > booking.total_amount:
                    return Response({'error': 'Advance amount cannot exceed total amount.'}, status=400)
                booking.advance_amount = advance
            except Exception:
                return Response({'error': 'Invalid advance amount.'}, status=400)

        booking.status = 'CONFIRMED'
        booking.save()  # full save so balance_amount recalculates

        import threading
        from .whatsapp_notification import send_holiday_orderform_whatsapp
        threading.Thread(target=send_holiday_orderform_whatsapp, args=(booking,), daemon=True).start()

        return Response({'success': True, 'message': f'Booking {booking.booking_number} confirmed!'})


# ─────────────────────────────────────────────────────────────────
# 7. UPDATE BOOKING
# ─────────────────────────────────────────────────────────────────

class MobileHolidayUpdateAPI(APIView):
    """POST /api/mobile/holidays/<pk>/update/"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        if booking.status == 'COMPLETED':
            return Response({'error': 'Completed trips cannot be edited.'}, status=400)
        try:
            if booking.settlement.bank.status == BankSettlement.STATUS_APPROVED:
                return Response({'error': 'Bank-approved trips cannot be edited.'}, status=400)
        except (TripSettlement.DoesNotExist, BankSettlement.DoesNotExist, AttributeError):
            pass

        data = request.data
        contact = str(data.get('contact_number', ''))
        if not re.match(r'^\d{10}$', contact):
            return Response({'error': 'Contact number must be exactly 10 digits.'}, status=400)
        second = data.get('second_contact_number')
        if second and not re.match(r'^\d{10}$', str(second)):
            return Response({'error': 'Second contact must be exactly 10 digits.'}, status=400)

        try:
            booked_vehicle = None
            vehicle_id = data.get('booked_vehicle')
            if vehicle_id:
                try:
                    booked_vehicle = Vehicle.objects.get(id=vehicle_id, company_id=company_id)
                except Vehicle.DoesNotExist:
                    pass

            booking.trip_date = data['trip_date']
            booking.purpose_of_booking = data.get('purpose_of_booking', '')
            booking.booked_by = data['booked_by']
            booking.contact_number = data['contact_number']
            booking.second_contact_number = second or None
            booking.departure_location = data['departure_location']
            booking.destination = data['destination']
            booking.departure_time = data['departure_time']
            booking.return_date = data.get('return_date') or None
            booking.return_time = data.get('return_time') or None
            booking.no_of_passengers = int(data.get('no_of_passengers', 1))
            booking.booked_vehicle = booked_vehicle
            booking.ac_type = data.get('ac_type', 'NON_AC')
            booking.payment_type_label = data.get('payment_type_label', '')
            booking.total_rent = Decimal(str(data.get('total_rent', 0) or 0))
            booking.service_charge = Decimal(str(data.get('service_charge', 0) or 0))
            booking.advance_amount = Decimal(str(data.get('advance_amount', 0) or 0))
            booking.max_km = int(data['max_km']) if data.get('max_km') else None
            booking.extra_km_charge = Decimal(str(data['extra_km_charge'])) if data.get('extra_km_charge') else None
            booking.special_instructions = data.get('special_instructions', '')
            booking.save()
            return Response({'success': True, 'message': f'Booking {booking.booking_number} updated!'})
        except KeyError as e:
            return Response({'error': f'Missing field: {e}'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────
# 8. DELETE BOOKING
# ─────────────────────────────────────────────────────────────────

class MobileHolidayDeleteAPI(APIView):
    """DELETE /api/mobile/holidays/<pk>/delete/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        has_perm, error = check_user_permission(request.user, 'can_delete_holiday', company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=company_id)
            try:
                if booking.settlement.bank.status == BankSettlement.STATUS_APPROVED:
                    return Response({'error': 'Cannot delete a bank-approved booking.'}, status=400)
            except (TripSettlement.DoesNotExist, BankSettlement.DoesNotExist, AttributeError):
                pass
            booking.delete()
            return Response({'success': True, 'message': 'Booking deleted.'})
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found.'}, status=404)


# ─────────────────────────────────────────────────────────────────
# 9. COMPLETED TRIPS (for settlement)
# ─────────────────────────────────────────────────────────────────

class MobileHolidayCompletedListAPI(APIView):
    """GET /api/mobile/holidays/completed/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        auto_complete_bookings(company_id)

        bookings = HolidayBooking.objects.filter(
            company_id=company_id, status='COMPLETED'
        ).select_related('booked_vehicle').order_by('-return_date', '-id')

        settlement_map = {
            s.booking_id: s.id
            for s in TripSettlement.objects.filter(booking__company_id=company_id)
        }

        data = [{
            'id': b.id,
            'booking_number': b.booking_number,
            'trip_date': b.trip_date.isoformat(),
            'return_date': b.return_date.isoformat() if b.return_date else None,
            'return_time': b.return_time.strftime('%H:%M') if b.return_time else None,
            'departure_time': b.departure_time.strftime('%H:%M') if b.departure_time else None,
            'destination': b.destination,
            'departure_location': b.departure_location,
            'booked_by': b.booked_by,
            'contact_number': b.contact_number,
            'booked_vehicle': str(b.booked_vehicle) if b.booked_vehicle else None,
            'booked_vehicle_id': b.booked_vehicle_id,
            'booked_vehicle_batta': str(b.booked_vehicle.batta_percentage) if b.booked_vehicle and b.booked_vehicle.batta_percentage else '0',
            'total_rent': str(b.total_rent or 0),
            'service_charge': str(b.service_charge or 0),
            'advance_amount': str(b.advance_amount or 0),
            'total_amount': str(b.total_amount or 0),
            'balance_amount': str(b.balance_amount or 0),
            'has_settlement': b.id in settlement_map,
            'settlement_id': settlement_map.get(b.id),
        } for b in bookings]

        return Response({'bookings': data})


# ─────────────────────────────────────────────────────────────────
# 10. GET SETTLEMENT
# ─────────────────────────────────────────────────────────────────

class MobileSettlementGetAPI(APIView):
    """GET /api/mobile/holidays/<pk>/settlement/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        try:
            s = booking.settlement
            custom = [{
                'id': c.id,
                'name': c.name,
                'amount': str(c.amount),
                'attachment_url': request.build_absolute_uri(c.attachment.url) if c.attachment else None,
                'attachment_name': c.attachment.name.split('/')[-1] if c.attachment else None,
            } for c in s.custom_charges.all()]

            bank_is_approved = False
            bank_id = None
            bank_status = None
            bank_doc_url = None
            try:
                bank_is_approved = s.bank.status == BankSettlement.STATUS_APPROVED
                bank_id = s.bank.id
                bank_status = s.bank.status
                bank_doc_url = request.build_absolute_uri(s.bank.bank_document.url) if s.bank.bank_document else None
            except BankSettlement.DoesNotExist:
                pass

            return Response({
                'exists': True,
                'settlement_id': s.id,
                'bank_is_approved': bank_is_approved,
                'bank_id': bank_id,
                'bank_status': bank_status,
                'bank_doc_url': bank_doc_url,
                'extra_rent': str(s.extra_rent or 0),
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
            return Response({'exists': False, 'settlement_id': None})


# ─────────────────────────────────────────────────────────────────
# 11. SAVE SETTLEMENT (multipart)
# ─────────────────────────────────────────────────────────────────

class MobileSettlementSaveAPI(APIView):
    """POST /api/mobile/holidays/<pk>/settlement/save/ (multipart/form-data)"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            booking = HolidayBooking.objects.get(pk=pk, company_id=company_id)
        except HolidayBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        try:
            if booking.settlement.bank.status == BankSettlement.STATUS_APPROVED:
                return Response({'error': 'Bank-approved settlement cannot be edited.'}, status=403)
        except (TripSettlement.DoesNotExist, BankSettlement.DoesNotExist):
            pass

        data = request.data
        files = request.FILES

        commission_pct = Decimal(str(data.get('commission_percentage', '0') or '0'))
        diesel_charge = Decimal(str(data.get('diesel_charge', '0') or '0'))
        cleaning_charge = Decimal(str(data.get('cleaning_charge', '0') or '0'))
        grease_charge = Decimal(str(data.get('grease_charge', '0') or '0'))
        batta_pct = Decimal(str(data.get('batta_percentage', '0') or '0'))
        extra_rent = Decimal(str(data.get('extra_rent', '0') or '0'))

        total_amount = Decimal(str(booking.total_rent or 0)) + extra_rent
        commission_amt = (total_amount * commission_pct / Decimal('100')).quantize(Decimal('0.01'))
        batta_amt = (total_amount * batta_pct / Decimal('100')).quantize(Decimal('0.01'))
        net_rent = total_amount - commission_amt - batta_amt

        custom_count = int(data.get('custom_count', 0) or 0)
        custom_total = Decimal('0')
        custom_rows = []
        for i in range(custom_count):
            name = data.get(f'custom_name_{i}', '').strip()
            amount = Decimal(str(data.get(f'custom_amount_{i}', '0') or '0'))
            file = files.get(f'custom_file_{i}')
            if name:
                custom_total += amount
                custom_rows.append((name, amount, file))

        net_balance = net_rent - batta_amt - diesel_charge - cleaning_charge - grease_charge - custom_total

        try:
            settlement = booking.settlement
        except TripSettlement.DoesNotExist:
            settlement = TripSettlement(booking=booking, created_by=request.user)

        settlement.extra_rent = extra_rent
        settlement.commission_percentage = commission_pct
        settlement.commission_amount = commission_amt
        settlement.net_rent = net_rent
        settlement.batta_percentage = batta_pct
        settlement.batta_amount = batta_amt
        settlement.diesel_charge = diesel_charge
        settlement.cleaning_charge = cleaning_charge
        settlement.grease_charge = grease_charge
        settlement.net_balance = net_balance

        if 'diesel_bill' in files:
            settlement.diesel_bill = files['diesel_bill']
        if 'grease_bill' in files:
            settlement.grease_bill = files['grease_bill']

        settlement.save()

        settlement.custom_charges.all().delete()
        for (name, amount, file) in custom_rows:
            charge = TripSettlementCharge(settlement=settlement, name=name.upper(), amount=amount)
            if file:
                charge.attachment = file
            charge.save()

        return Response({'success': True, 'message': 'Settlement saved!', 'settlement_id': settlement.id})


# ─────────────────────────────────────────────────────────────────
# 12. BANK LIST
# ─────────────────────────────────────────────────────────────────

class MobileBankListAPI(APIView):
    """GET /api/mobile/holidays/bank/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        settlements = TripSettlement.objects.filter(
            booking__company_id=company_id
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
                    'document_url': request.build_absolute_uri(bank.bank_document.url) if bank.bank_document else None,
                    'document_name': bank.bank_document.name.split('/')[-1] if bank.bank_document else None,
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


# ─────────────────────────────────────────────────────────────────
# 13. BANK DOCUMENT UPLOAD
# ─────────────────────────────────────────────────────────────────

class MobileBankUploadAPI(APIView):
    """POST /api/mobile/holidays/bank/<settlement_pk>/upload/ (multipart)"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, settlement_pk):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        try:
            settlement = TripSettlement.objects.get(
                pk=settlement_pk, booking__company_id=company_id
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

        return Response({'success': True, 'bank_id': bank.id, 'message': 'Document uploaded. Pending approval.'})


# ─────────────────────────────────────────────────────────────────
# 14. BANK APPROVE
# ─────────────────────────────────────────────────────────────────

class MobileBankApproveAPI(APIView):
    """POST /api/mobile/holidays/bank/<bank_pk>/approve/"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, bank_pk):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        is_approver = HolidayBankApprover.objects.filter(
            company_id=company_id, user=request.user, is_active=True
        ).exists()
        if not request.user.is_superuser and not is_approver:
            return Response({'error': 'You do not have approval permission.'}, status=403)

        try:
            bank = BankSettlement.objects.get(pk=bank_pk)
        except BankSettlement.DoesNotExist:
            return Response({'error': 'Bank settlement not found.'}, status=404)

        bank.status = BankSettlement.STATUS_APPROVED
        bank.approved_by = request.user
        bank.approved_at = timezone.now()
        bank.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        return Response({'success': True, 'message': 'Settlement approved.'})


# ─────────────────────────────────────────────────────────────────
# 15. MASTER DATA — VEHICLES
# ─────────────────────────────────────────────────────────────────

class MobileVehicleListAPI(APIView):
    """GET /api/mobile/vehicles/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        vehicles = Vehicle.objects.filter(
            company_id=company_id, is_active=True
        ).order_by('name')

        data = [{
            'id': v.id,
            'name': v.name,
            'registration_number': v.registration_number,
            'batta_percentage': str(v.batta_percentage) if v.batta_percentage else '0',
        } for v in vehicles]

        return Response({'vehicles': data})


# ─────────────────────────────────────────────────────────────────
# 16. MASTER DATA — PAYMENT TYPES
# ─────────────────────────────────────────────────────────────────

class MobilePaymentTypeListAPI(APIView):
    """GET /api/mobile/payment-types/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        payment_types = PaymentType.objects.filter(
            company_id=company_id, is_active=True
        ).order_by('name')

        return Response({'payment_types': [{'id': pt.id, 'name': pt.name} for pt in payment_types]})


# ─────────────────────────────────────────────────────────────────
# 17. REPAIR — LIST
# ─────────────────────────────────────────────────────────────────

class MobileRepairListAPI(APIView):
    """GET /api/mobile/repairs/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        repairs = RepairMaintenance.objects.filter(
            company_id=company_id
        ).select_related('vehicle').prefetch_related('items').order_by('-created_at')

        data = []
        for r in repairs:
            try:
                bank = r.bank
                bank_status = bank.status
                bank_id = bank.id
            except RepairBankSettlement.DoesNotExist:
                bank_status = None
                bank_id = None

            data.append({
                'id': r.id,
                'repair_number': r.repair_number,
                'vehicle': str(r.vehicle) if r.vehicle else None,
                'vehicle_id': r.vehicle_id,
                'status': r.status,
                'total_amount': str(r.total_amount),
                'notes': r.notes or '',
                'created_at': r.created_at.strftime('%d %b %Y'),
                'items_count': r.items.count(),
                'bank_status': bank_status,
                'bank_id': bank_id,
            })

        return Response({'repairs': data})


# ─────────────────────────────────────────────────────────────────
# 18. REPAIR — CREATE (multipart)
# ─────────────────────────────────────────────────────────────────

class MobileRepairCreateAPI(APIView):
    """POST /api/mobile/repairs/create/ (multipart/form-data)"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        try:
            company = Company.objects.get(id=company_id)
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
        starting_km_raw  = (data.get('starting_km') or '').strip()
        ending_km_raw    = (data.get('ending_km') or '').strip()
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
            import traceback; traceback.print_exc()
            return Response({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────
# 19. REPAIR — DETAIL
# ─────────────────────────────────────────────────────────────────

class MobileRepairDetailAPI(APIView):
    """GET /api/mobile/repairs/<pk>/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        try:
            repair = RepairMaintenance.objects.select_related('vehicle').prefetch_related('items').get(
                pk=pk, company_id=company_id
            )
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found'}, status=404)

        try:
            bank = repair.bank
            bank_status = bank.status
            bank_id = bank.id
            bank_doc_url = request.build_absolute_uri(bank.bank_document.url) if bank.bank_document else None
            approved_by = bank.approved_by.get_full_name() or bank.approved_by.username if bank.approved_by else None
            approved_at = bank.approved_at.strftime('%d %b %Y, %H:%M') if bank.approved_at else None
        except RepairBankSettlement.DoesNotExist:
            bank_status = bank_id = bank_doc_url = approved_by = approved_at = None

        items = [{
            'id': item.id,
            'name': item.name,
            'description': item.description or '',
            'amount': str(item.amount),
            'attachment_url': request.build_absolute_uri(item.attachment.url) if item.attachment else None,
            'attachment_name': item.attachment.name.split('/')[-1] if item.attachment else None,
        } for item in repair.items.all()]

        return Response({
            'id': repair.id,
            'repair_number': repair.repair_number,
            'vehicle': str(repair.vehicle) if repair.vehicle else None,
            'vehicle_id': repair.vehicle_id,
            'status': repair.status,
            'total_amount': str(repair.total_amount),
            'notes': repair.notes or '',
            'starting_km': repair.starting_km,
            'starting_km_attachment_url': request.build_absolute_uri(repair.starting_km_attachment.url) if repair.starting_km_attachment else None,
            'ending_km': repair.ending_km,
            'ending_km_attachment_url': request.build_absolute_uri(repair.ending_km_attachment.url) if repair.ending_km_attachment else None,
            'created_at': repair.created_at.strftime('%d %b %Y'),
            'items': items,
            'bank_status': bank_status,
            'bank_id': bank_id,
            'bank_doc_url': bank_doc_url,
            'approved_by': approved_by,
            'approved_at': approved_at,
        })


# ─────────────────────────────────────────────────────────────────
# 20. REPAIR — SUBMIT TO BANK (multipart)
# ─────────────────────────────────────────────────────────────────

class MobileRepairSubmitBankAPI(APIView):
    """POST /api/mobile/repairs/<pk>/submit-to-bank/ (multipart)"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=company_id)
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found'}, status=404)

        doc = request.FILES.get('bank_document')
        if not doc:
            return Response({'error': 'A bank document is required to submit for approval.'}, status=400)

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
        return Response({'success': True, 'bank_id': bank.id, 'message': 'Submitted to bank.'})


# ─────────────────────────────────────────────────────────────────
# 21. REPAIR — BANK APPROVE
# ─────────────────────────────────────────────────────────────────

class MobileRepairBankApproveAPI(APIView):
    """POST /api/mobile/repairs/<pk>/bank/approve/"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        is_approver = HolidayBankApprover.objects.filter(
            company_id=company_id, user=request.user, is_active=True
        ).exists()
        if not request.user.is_superuser and not is_approver:
            return Response({'error': 'You do not have approval permission.'}, status=403)

        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=company_id)
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found'}, status=404)

        try:
            bank = repair.bank
        except RepairBankSettlement.DoesNotExist:
            return Response({'error': 'No bank settlement found for this repair.'}, status=404)

        bank.status = RepairBankSettlement.STATUS_APPROVED
        bank.approved_by = request.user
        bank.approved_at = timezone.now()
        bank.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

        repair.status = RepairMaintenance.STATUS_APPROVED
        repair.save(update_fields=['status', 'updated_at'])
        return Response({'success': True, 'message': 'Repair approved.'})


# ─────────────────────────────────────────────────────────────────
# 22. REPAIR — DELETE
# ─────────────────────────────────────────────────────────────────

class MobileRepairDeleteAPI(APIView):
    """DELETE /api/mobile/repairs/<pk>/delete/?company_id=<id>"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        company_id = request.query_params.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        has_perm, error = check_user_permission(request.user, 'can_delete_holiday', company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=company_id)
            if repair.status == RepairMaintenance.STATUS_APPROVED:
                return Response({'error': 'Cannot delete an approved repair.'}, status=400)
            repair.delete()
            return Response({'success': True, 'message': 'Repair deleted.'})
        except RepairMaintenance.DoesNotExist:
            return Response({'error': 'Repair not found.'}, status=404)


# ─────────────────────────────────────────────────────────────────
# 23. REPAIR — UPDATE (multipart)
# ─────────────────────────────────────────────────────────────────

class MobileRepairUpdateAPI(APIView):
    """POST /api/mobile/repairs/<pk>/update/ (multipart/form-data)

    Preserves existing item attachments unless replaced. Each item may send:
      item_id_<i>          existing RepairItem id (omit for new items)
      item_name_<i>        required
      item_description_<i>
      item_amount_<i>
      item_attachment_<i>  new file (optional; keeps old if absent)
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company_id = request.data.get('company_id')
        if not _has_company_access(request.user, company_id):
            return Response({'error': 'Access denied'}, status=403)

        has_perm, error = check_user_permission(request.user, 'can_edit_holiday', company_id)
        if not has_perm:
            return Response({'error': error}, status=403)

        try:
            repair = RepairMaintenance.objects.get(pk=pk, company_id=company_id)
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

        data = request.data
        files = request.FILES

        vehicle_id = data.get('vehicle_id')
        if vehicle_id:
            try:
                repair.vehicle = Vehicle.objects.get(id=vehicle_id, company_id=company_id)
            except Vehicle.DoesNotExist:
                pass
        else:
            repair.vehicle = None
        repair.notes = data.get('notes', repair.notes or '')

        # KM fields — mandatory on update
        starting_km_raw  = (data.get('starting_km') or '').strip()
        ending_km_raw    = (data.get('ending_km') or '').strip()
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

        # Parse submitted items
        parsed = []
        idx = 0
        while True:
            name = data.get(f'item_name_{idx}')
            if not name:
                break
            try:
                amount = Decimal(str(data.get(f'item_amount_{idx}', '0') or '0'))
            except Exception:
                amount = Decimal('0')
            parsed.append({
                'item_id': data.get(f'item_id_{idx}'),
                'name': name,
                'description': data.get(f'item_description_{idx}', ''),
                'amount': amount,
                'file': files.get(f'item_attachment_{idx}'),
            })
            idx += 1

        if not parsed:
            return Response({'error': 'At least one repair item is required.'}, status=400)

        # Delete items no longer present
        kept_ids = [int(p['item_id']) for p in parsed if p['item_id']]
        repair.items.exclude(id__in=kept_ids).delete()

        # Update existing / create new (preserving attachments)
        for p in parsed:
            if p['item_id']:
                try:
                    ri = repair.items.get(id=p['item_id'])
                except RepairItem.DoesNotExist:
                    ri = RepairItem(repair=repair)
            else:
                ri = RepairItem(repair=repair)
            ri.name = p['name']
            ri.description = p['description']
            ri.amount = p['amount']
            if p['file']:
                ri.attachment = p['file']
            ri.save()

        repair.total_amount = sum(p['amount'] for p in parsed)
        repair.status = RepairMaintenance.STATUS_DRAFT
        repair.save()

        return Response({'success': True, 'message': 'Repair updated.'})
