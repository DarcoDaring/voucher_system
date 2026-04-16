# vouchers/mobile_api.py
#
# ─────────────────────────────────────────────────────────────────
#  NEW FILE – does NOT modify any existing view/serializer/model.
#  Add this file to the vouchers/ app directory.
# ─────────────────────────────────────────────────────────────────
#
# Django settings change required (settings.py):
#   Add 'rest_framework.authtoken' to INSTALLED_APPS
#   Then run: python manage.py migrate
#
# urls.py change required – add these 4 lines inside urlpatterns:
#   from vouchers.mobile_api import (
#       MobileLoginAPI, MobileVoucherListAPI,
#       MobileVoucherDetailAPI, MobileVoucherApprovalAPI
#   )
#   path('api/mobile/login/',                    MobileLoginAPI.as_view(),          name='mobile_login'),
#   path('api/mobile/vouchers/',                 MobileVoucherListAPI.as_view(),    name='mobile_voucher_list'),
#   path('api/mobile/vouchers/<int:pk>/',        MobileVoucherDetailAPI.as_view(),  name='mobile_voucher_detail'),
#   path('api/mobile/vouchers/<int:pk>/action/', MobileVoucherApprovalAPI.as_view(),name='mobile_voucher_action'),

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.db import transaction, OperationalError
from django.db.models import Count, Case, When, IntegerField
import time

from .models import (
    Voucher, VoucherApproval, ApprovalLevel,
    Company, CompanyMembership,
)


# ──────────────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────────────

def _verify_company_access(user, company_id, require_admin_staff=False):
    """
    Returns True if the user has access to the given company.
    Superusers always pass.
    """
    if user.is_superuser:
        return Company.objects.filter(id=company_id, is_active=True).exists()

    qs = CompanyMembership.objects.filter(
        user=user,
        company_id=company_id,
        is_active=True,
        company__is_active=True,
    )
    if require_admin_staff:
        qs = qs.filter(group='Admin Staff')
    return qs.exists()


def _get_approval_status(voucher, user, company_id):
    """
    Returns (can_approve: bool, waiting_for: str|None)
    for the given user on this voucher.
    """
    if voucher.status != 'PENDING':
        return False, None
    if user.username not in voucher.required_approvers:
        return False, None

    levels = ApprovalLevel.objects.filter(
        company_id=company_id, is_active=True
    ).order_by('order')

    approved_usernames = set(
        voucher.approvals.filter(status='APPROVED')
        .values_list('approver__username', flat=True)
    )

    current_user_level = None
    for level in levels:
        users_in_level = list(
            CompanyMembership.objects.filter(
                company_id=company_id,
                designation=level.designation,
                group='Admin Staff',
                is_active=True,
                user__is_active=True,
            ).values_list('user__username', flat=True)
        )
        if user.username in users_in_level:
            current_user_level = level
            break

    if not current_user_level:
        return False, None

    prev_level = ApprovalLevel.objects.filter(
        company_id=company_id,
        order__lt=current_user_level.order,
        is_active=True,
    ).order_by('-order').first()

    if not prev_level:
        return True, None

    prev_users = list(
        CompanyMembership.objects.filter(
            company_id=company_id,
            designation=prev_level.designation,
            group='Admin Staff',
            is_active=True,
            user__is_active=True,
        ).values_list('user__username', flat=True)
    )

    if any(u in approved_usernames for u in prev_users):
        return True, None

    return False, prev_level.designation.name


# ──────────────────────────────────────────────────────────────────
# 1. LOGIN
# ──────────────────────────────────────────────────────────────────

class MobileLoginAPI(APIView):
    """
    POST /api/mobile/login/
    Body: { "username": "...", "password": "..." }

    Returns token + list of companies the user belongs to.
    No session / cookie needed for subsequent requests.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=400)

        user = authenticate(username=username, password=password)

        if not user:
            return Response({'error': 'Invalid username or password.'}, status=401)

        if not user.is_active:
            return Response({'error': 'This account is disabled.'}, status=401)

        token, _ = Token.objects.get_or_create(user=user)

        # Build company list
        if user.is_superuser:
            companies = Company.objects.filter(is_active=True).order_by('name')
            company_list = [
                {
                    'id': c.id,
                    'name': c.name,
                    'logo_url': request.build_absolute_uri(c.logo.url) if c.logo else None,
                    'role': 'Admin Staff',
                    'designation': None,
                }
                for c in companies
            ]
        else:
            memberships = CompanyMembership.objects.filter(
                user=user, is_active=True, company__is_active=True
            ).select_related('company', 'designation').order_by('company__name')

            if not memberships.exists():
                return Response(
                    {'error': 'You are not assigned to any active company.'},
                    status=403,
                )

            company_list = [
                {
                    'id': m.company.id,
                    'name': m.company.name,
                    'logo_url': request.build_absolute_uri(m.company.logo.url)
                    if m.company.logo
                    else None,
                    'role': m.group,
                    'designation': m.designation.name if m.designation else None,
                }
                for m in memberships
            ]

        return Response(
            {
                'token': token.key,
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'is_superuser': user.is_superuser,
                'companies': company_list,
            }
        )


# ──────────────────────────────────────────────────────────────────
# 2. VOUCHER LIST
# ──────────────────────────────────────────────────────────────────

class MobileVoucherListAPI(APIView):
    """
    GET /api/mobile/vouchers/?company_id=<id>&status=<PENDING|APPROVED|REJECTED>

    Returns paginated voucher list for the selected company.
    Passes Authorization: Token <key> header.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get('company_id')
        status_filter = request.query_params.get('status', '')  # optional filter

        if not company_id:
            return Response({'error': 'company_id query param is required.'}, status=400)

        if not _verify_company_access(request.user, company_id):
            return Response({'error': 'Access denied for this company.'}, status=403)

        qs = Voucher.objects.filter(
            company_id=company_id
        ).select_related(
            'created_by', 'account_details'
        ).prefetch_related(
            'particulars', 'approvals__approver'
        ).order_by('-created_at').annotate(
            approved_count=Count(
                Case(When(approvals__status='APPROVED', then=1)),
                output_field=IntegerField(),
            ),
            rejected_count=Count(
                Case(When(approvals__status='REJECTED', then=1)),
                output_field=IntegerField(),
            ),
        )

        if status_filter in ('PENDING', 'APPROVED', 'REJECTED'):
            qs = qs.filter(status=status_filter)

        # Pre-fetch approval levels once for the company
        levels = list(
            ApprovalLevel.objects.filter(
                company_id=company_id, is_active=True
            ).select_related('designation').order_by('order')
        )

        data = []
        for v in qs:
            total_amount = sum(p.amount for p in v.particulars.all())
            can_approve, _ = _get_approval_status(v, request.user, company_id)

            # --- waiting_for_username logic (mirrors web VoucherListView) ---
            waiting_for_username = None
            if v.status == 'PENDING':
                approved_usernames = set(
                    v.approvals.filter(status='APPROVED')
                    .values_list('approver__username', flat=True)
                )
                first_pending_level = None
                for lvl in levels:
                    level_user_ids = list(
                        CompanyMembership.objects.filter(
                            company_id=company_id,
                            designation=lvl.designation,
                            group='Admin Staff',
                            is_active=True,
                            user__is_active=True,
                        ).values_list('user__id', flat=True)
                    )
                    approved_in_level = v.approvals.filter(
                        status='APPROVED',
                        approver__id__in=level_user_ids,
                    ).count()
                    if approved_in_level < len(level_user_ids):
                        first_pending_level = lvl
                        break

                if first_pending_level:
                    pending_users = list(
                        CompanyMembership.objects.filter(
                            company_id=company_id,
                            designation=first_pending_level.designation,
                            group='Admin Staff',
                            is_active=True,
                            user__is_active=True,
                        ).exclude(
                            user__id__in=v.approvals.filter(
                                status='APPROVED'
                            ).values_list('approver__id', flat=True)
                        ).values_list('user__username', flat=True)
                    )
                    waiting_for_username = ', '.join(pending_users) if pending_users else None
            # -------------------------------------------------------------------

            data.append(
                {
                    'id': v.id,
                    'voucher_number': v.voucher_number,
                    'voucher_date': str(v.voucher_date),
                    'payment_type': v.payment_type,
                    'pay_to': v.pay_to,
                    'pay_to_display': f"{v.get_name_title_display()} {v.pay_to}",
                    'status': v.status,
                    'total_amount': str(total_amount),
                    'created_by': v.created_by.username,
                    'created_at': v.created_at.strftime('%d %b %Y'),
                    'can_approve': can_approve,
                    'waiting_for_username': waiting_for_username,
                    'approved_count': v.approved_count,
                    'required_approvers_count': len(v.required_approvers),
                }
            )

        return Response({'vouchers': data, 'count': len(data)})


# ──────────────────────────────────────────────────────────────────
# 3. VOUCHER DETAIL
# ──────────────────────────────────────────────────────────────────

class MobileVoucherDetailAPI(APIView):
    """
    GET /api/mobile/vouchers/<pk>/?company_id=<id>
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        company_id = request.query_params.get('company_id')
        if not company_id:
            return Response({'error': 'company_id query param is required.'}, status=400)

        if not _verify_company_access(request.user, company_id):
            return Response({'error': 'Access denied for this company.'}, status=403)

        try:
            voucher = (
                Voucher.objects.filter(company_id=company_id)
                .select_related('created_by', 'account_details')
                .prefetch_related(
                    'particulars__attachments',
                    'approvals__approver',
                    'main_attachments',
                    'cheque_attachments',
                )
                .get(pk=pk)
            )
        except Voucher.DoesNotExist:
            return Response({'error': 'Voucher not found.'}, status=404)

        # Approvals
        approvals_data = [
            {
                'approver': a.approver.username,
                'status': a.status,
                'approved_at': a.approved_at.strftime('%d %b %Y, %H:%M')
                if a.approved_at
                else None,
                'rejection_reason': a.rejection_reason,
            }
            for a in voucher.approvals.all().order_by('approved_at')
        ]

        # User's own approval record
        user_approval = voucher.approvals.filter(approver=request.user).first()

        # Can this user approve right now?
        can_approve, waiting_for = _get_approval_status(voucher, request.user, company_id)

        # Particulars + per-particular attachments
        particulars_data = [
            {
                'id': p.id,
                'description': p.description,
                'amount': str(p.amount),
                'attachments': [
                    {
                        'id': a.id,
                        'url': request.build_absolute_uri(a.file.url) if a.file else None,
                        'filename': a.file.name.split('/')[-1] if a.file else '',
                    }
                    for a in p.attachments.all()
                ],
            }
            for p in voucher.particulars.all()
        ]

        total_amount = sum(float(p['amount']) for p in particulars_data)

        main_attachments = [
            {
                'id': a.id,
                'url': request.build_absolute_uri(a.file.url) if a.file else None,
                'filename': a.file.name.split('/')[-1] if a.file else '',
            }
            for a in voucher.main_attachments.all()
        ]

        cheque_attachments = [
            {
                'id': a.id,
                'url': request.build_absolute_uri(a.file.url) if a.file else None,
                'filename': a.file.name.split('/')[-1] if a.file else '',
            }
            for a in voucher.cheque_attachments.all()
        ]

        return Response(
            {
                'id': voucher.id,
                'voucher_number': voucher.voucher_number,
                'voucher_date': str(voucher.voucher_date),
                'payment_type': voucher.payment_type,
                'name_title': voucher.name_title,
                'pay_to': voucher.pay_to,
                'pay_to_display': f"{voucher.get_name_title_display()} {voucher.pay_to}",
                'cheque_number': voucher.cheque_number,
                'cheque_date': str(voucher.cheque_date) if voucher.cheque_date else None,
                'account_details': str(voucher.account_details)
                if voucher.account_details
                else None,
                'status': voucher.status,
                'total_amount': f"{total_amount:.2f}",
                'created_by': voucher.created_by.username,
                'created_at': voucher.created_at.strftime('%d %b %Y, %H:%M'),
                'particulars': particulars_data,
                'main_attachments': main_attachments,
                'cheque_attachments': cheque_attachments,
                'approvals': approvals_data,
                'required_approvers': voucher.required_approvers,
                'required_approvers_count': len(voucher.required_approvers),
                'can_approve': can_approve,
                'waiting_for': waiting_for,
                'user_approval_status': user_approval.status if user_approval else None,
            }
        )


# ──────────────────────────────────────────────────────────────────
# 4. APPROVE / REJECT
# ──────────────────────────────────────────────────────────────────

class MobileVoucherApprovalAPI(APIView):
    """
    POST /api/mobile/vouchers/<pk>/action/
    Body: {
        "company_id": <int>,
        "action": "APPROVED" | "REJECTED",
        "rejection_reason": "..."   # required when action == REJECTED
    }
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        company_id = request.data.get('company_id')
        action = request.data.get('action', '').upper()
        rejection_reason = request.data.get('rejection_reason', '').strip()

        if not company_id:
            return Response({'error': 'company_id is required.'}, status=400)

        if action not in ('APPROVED', 'REJECTED'):
            return Response(
                {'error': 'action must be APPROVED or REJECTED.'}, status=400
            )

        if action == 'REJECTED' and not rejection_reason:
            return Response(
                {'error': 'rejection_reason is required when rejecting.'}, status=400
            )

        # Must be Admin Staff to approve
        if not _verify_company_access(request.user, company_id, require_admin_staff=True):
            return Response(
                {'error': 'Only Admin Staff members can approve vouchers.'}, status=403
            )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    voucher = Voucher.objects.select_for_update(nowait=True).get(
                        pk=pk, company_id=company_id
                    )

                    if request.user.username not in voucher.required_approvers:
                        return Response(
                            {'error': 'You are not in the approval chain for this voucher.'},
                            status=403,
                        )

                    if voucher.status != 'PENDING':
                        return Response(
                            {'error': 'This voucher is no longer pending.'}, status=400
                        )

                    # Validate sequential approval order
                    levels = ApprovalLevel.objects.filter(
                        company_id=company_id, is_active=True
                    ).order_by('order')

                    approved_usernames = set(
                        voucher.approvals.filter(status='APPROVED').values_list(
                            'approver__username', flat=True
                        )
                    )

                    current_user_level = None
                    for level in levels:
                        users_in_level = list(
                            CompanyMembership.objects.filter(
                                company_id=company_id,
                                designation=level.designation,
                                group='Admin Staff',
                                is_active=True,
                                user__is_active=True,
                            ).values_list('user__username', flat=True)
                        )
                        if request.user.username in users_in_level:
                            current_user_level = level
                            break

                    if not current_user_level:
                        return Response(
                            {'error': 'Your designation is not part of any approval level.'},
                            status=403,
                        )

                    prev_level = ApprovalLevel.objects.filter(
                        company_id=company_id,
                        order__lt=current_user_level.order,
                        is_active=True,
                    ).order_by('-order').first()

                    if prev_level:
                        prev_users = list(
                            CompanyMembership.objects.filter(
                                company_id=company_id,
                                designation=prev_level.designation,
                                group='Admin Staff',
                                is_active=True,
                                user__is_active=True,
                            ).values_list('user__username', flat=True)
                        )
                        if not any(u in approved_usernames for u in prev_users):
                            return Response(
                                {
                                    'error': f'Waiting for {prev_level.designation.name} to approve first.'
                                },
                                status=403,
                            )

                    approval, _ = VoucherApproval.objects.update_or_create(
                        voucher=voucher,
                        approver=request.user,
                        defaults={
                            'status': action,
                            'rejection_reason': rejection_reason
                            if action == 'REJECTED'
                            else None,
                        },
                    )

                    voucher.refresh_from_db()
                    voucher._update_status_if_all_approved()

                return Response(
                    {
                        'success': True,
                        'message': f'Voucher {action.lower()} successfully.',
                        'voucher_status': voucher.status,
                        'approval': {
                            'approver': request.user.username,
                            'status': action,
                            'approved_at': approval.approved_at.strftime('%d %b %Y, %H:%M'),
                            'rejection_reason': approval.rejection_reason,
                        },
                    }
                )

            except OperationalError as e:
                if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                return Response(
                    {'error': 'Database is busy. Please try again in a moment.'}, status=503
                )
            except Voucher.DoesNotExist:
                return Response({'error': 'Voucher not found.'}, status=404)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response({'error': str(e)}, status=500)

        return Response(
            {'error': 'Failed due to database lock. Please retry.'}, status=503
        )