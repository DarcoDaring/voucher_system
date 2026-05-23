from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Case, When, IntegerField
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import (
    Voucher, Particular, VoucherApproval, Designation,
    ApprovalLevel, UserProfile, AccountDetail, Company, CompanyMembership,
    MainAttachment, ChequeAttachment, ParticularAttachment, OnlineAttachment,
    FunctionBooking, HolidayBooking
)
from .serializers import VoucherSerializer, VoucherApprovalSerializer, AccountDetailSerializer
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password
from django.db import transaction, OperationalError
from django.db.models import F
from decimal import Decimal, InvalidOperation
import time
from datetime import datetime
from django.utils import timezone
from .models import UserPermission, CompanyMembership
from django.views import View
from django.contrib.auth import authenticate, login as auth_login, logout
from .whatsapp_notification import notify_approvers_new_voucher

from vouchers.mobile_api import (
    MobileLoginAPI, MobileVoucherListAPI,
    MobileVoucherDetailAPI, MobileVoucherApprovalAPI,
)


def get_user_designation_for_company(user, company_id):
    if not company_id:
        return None
    membership = CompanyMembership.objects.filter(
        user=user,
        company_id=company_id,
        is_active=True
    ).select_related('designation').first()
    return membership.designation if membership else None


def check_user_permission(user, permission_name, company_id=None):
    if user.is_superuser:
        return True, None

    if not company_id:
        return False, "No active company selected."

    try:
        perms = UserPermission.objects.filter(
            user=user,
            company_id=company_id
        ).first()

        if not perms:
            if permission_name in ['can_create_voucher', 'can_create_function',
                                   'can_view_voucher_list', 'can_view_voucher_detail', 'can_print_voucher',
                                   'can_view_function_list', 'can_view_function_detail', 'can_print_function',
                                   'can_view_holiday_list', 'can_view_holiday_detail', 'can_create_holiday']:
                return True, None
            return False, "You don't have permission to perform this action."

        has_perm = getattr(perms, permission_name, False)

        if not has_perm:
            permission_labels = {
                'can_create_voucher': 'create vouchers',
                'can_edit_voucher': 'edit vouchers',
                'can_view_voucher_list': 'view voucher list',
                'can_view_voucher_detail': 'view voucher details',
                'can_print_voucher': 'print vouchers',
                'can_create_function': 'create functions',
                'can_edit_function': 'edit functions',
                'can_delete_function': 'delete functions',
                'can_view_function_list': 'view function calendar',
                'can_view_function_detail': 'view function details',
                'can_print_function': 'print function prospectus',
                'can_create_holiday': 'create holiday bookings',
                'can_edit_holiday': 'edit holiday bookings',
                'can_delete_holiday': 'delete holiday bookings',
                'can_view_holiday_list': 'view holiday calendar',
                'can_view_holiday_detail': 'view holiday booking details',
            }
            label = permission_labels.get(permission_name, 'perform this action')
            return False, f"You don't have permission to {label}."

        return True, None

    except Exception as e:
        print(f"Error checking permission: {e}")
        if permission_name in ['can_create_voucher', 'can_create_function',
                               'can_view_voucher_list', 'can_view_voucher_detail', 'can_print_voucher',
                               'can_view_function_list', 'can_view_function_detail', 'can_print_function',
                               'can_view_holiday_list', 'can_view_holiday_detail', 'can_create_holiday']:
            return True, None
        return False, "You don't have permission to perform this action."

    except UserPermission.DoesNotExist:
        if permission_name in ['can_create_voucher', 'can_create_function',
                               'can_view_voucher_list', 'can_view_voucher_detail', 'can_print_voucher',
                               'can_view_function_list', 'can_view_function_detail', 'can_print_function',
                               'can_view_holiday_list', 'can_view_holiday_detail', 'can_create_holiday']:
            return True, None
        return False, "You don't have permission to perform this action."


# === MIXINS ===
class AccountantRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                return JsonResponse({'error': 'Authentication required.'}, status=401)
            return self.handle_no_permission()

        if not request.user.groups.filter(name='Accountants').exists():
            error_msg = "Only Accountants can perform this action."
            if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                return JsonResponse({'error': error_msg}, status=403)
            messages.error(request, error_msg)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)


class AdminStaffRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                return JsonResponse({'error': 'Authentication required.'}, status=401)
            return self.handle_no_permission()

        if not (request.user.groups.filter(name='Admin Staff').exists() or request.user.is_superuser):
            error_msg = "Only Admin Staff can perform this action."
            if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                return JsonResponse({'error': error_msg}, status=403)
            messages.error(request, error_msg)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)


# =============================================
# AUTHENTICATION & COMPANY SELECTION VIEWS
# =============================================

class CustomLoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            if request.user.is_superuser:
                return redirect('home')
            return redirect('select_company')
        return render(request, 'login.html')

    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, "Please enter both username and password")
            return redirect('login')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)

            if 'active_company_id' in request.session:
                del request.session['active_company_id']

            print(f"\n{'='*50}")
            print(f"DEBUG: Login successful for {user.username}")
            print(f"Is Superuser: {user.is_superuser}")

            if user.is_superuser:
                print(f"Superuser detected - setting up company access")
                company = Company.objects.filter(is_active=True).first()

                if not company:
                    print(f"No companies exist - creating default")
                    company = Company.objects.create(
                        name='Default Company',
                        is_active=True,
                        created_by=user
                    )
                    messages.info(request, f"Created default company: {company.name}")

                membership, created = CompanyMembership.objects.get_or_create(
                    user=user,
                    company=company,
                    defaults={
                        'group': 'Admin Staff',
                        'is_active': True
                    }
                )

                request.session['active_company_id'] = company.id
                print(f"Set active_company_id to {company.id} ({company.name})")
                print(f"Redirecting to home")
                print(f"{'='*50}\n")
                messages.success(request, f"Welcome, {user.username}! Currently viewing: {company.name}")
                return redirect('home')

            memberships = CompanyMembership.objects.filter(
                user=user,
                is_active=True,
                company__is_active=True
            ).select_related('company')

            membership_count = memberships.count()
            print(f"Regular user - Found {membership_count} active company memberships")

            if membership_count == 0:
                print(f"No memberships - logging out")
                print(f"{'='*50}\n")
                messages.error(request, "You are not assigned to any company. Please contact your administrator.")
                logout(request)
                return redirect('login')

            company_names = [m.company.name for m in memberships]
            print(f"Companies: {company_names}")
            print(f"Redirecting to select_company view")
            print(f"{'='*50}\n")

            return redirect('select_company')
        else:
            print(f"DEBUG: Login failed for username: {username}")
            messages.error(request, "Invalid username or password")
            return redirect('login')


class SelectCompanyView(LoginRequiredMixin, View):
    def get(self, request):
        print(f"\n{'='*50}")
        print(f"DEBUG: SelectCompanyView called")
        print(f"User: {request.user.username}")
        print(f"Is Superuser: {request.user.is_superuser}")

        if request.user.is_superuser:
            all_companies = Company.objects.filter(is_active=True).order_by('name')
            print(f"Superuser - Found {all_companies.count()} active companies")

            if not all_companies.exists():
                company = Company.objects.create(
                    name='Default Company',
                    is_active=True,
                    created_by=request.user
                )
                request.session['active_company_id'] = company.id
                messages.success(request, f"Created and switched to {company.name}")
                return redirect('home')

            memberships = []
            for company in all_companies:
                membership, _ = CompanyMembership.objects.get_or_create(
                    user=request.user,
                    company=company,
                    defaults={
                        'group': 'Admin Staff',
                        'is_active': True
                    }
                )
                memberships.append(membership)

            print(f"Memberships created: {len(memberships)}")

            if len(memberships) == 1:
                print(f"Only 1 company - auto-selecting: {memberships[0].company.name}")
                request.session['active_company_id'] = memberships[0].company.id
                messages.success(request, f"Switched to {memberships[0].company.name}")
                return redirect('home')

            print(f"Multiple companies ({len(memberships)}) - showing selection page")
            print(f"Companies: {[m.company.name for m in memberships]}")
            print(f"Rendering template: select_company.html")
            print(f"{'='*50}\n")

            return render(request, 'select_company.html', {
                'memberships': memberships
            })

        memberships = CompanyMembership.objects.filter(
            user=request.user,
            is_active=True,
            company__is_active=True
        ).select_related('company', 'designation')

        print(f"Regular user - Found {memberships.count()} active memberships")

        if not memberships.exists():
            print(f"No memberships found - logging out user")
            messages.error(request, "You are not assigned to any company. Please contact your administrator.")
            logout(request)
            return redirect('login')

        if memberships.count() == 1:
            print(f"Only 1 membership - auto-selecting: {memberships.first().company.name}")
            request.session['active_company_id'] = memberships.first().company.id
            messages.success(request, f"Switched to {memberships.first().company.name}")
            return redirect('home')

        print(f"Multiple memberships ({memberships.count()}) - showing selection page")
        print(f"Companies: {[m.company.name for m in memberships]}")
        print(f"Rendering template: select_company.html")
        print(f"{'='*50}\n")

        return render(request, 'select_company.html', {
            'memberships': memberships
        })


class SetCompanyView(LoginRequiredMixin, View):
    def post(self, request):
        company_id = request.POST.get('company_id')

        if not company_id:
            messages.error(request, "Please select a company")
            return redirect('select_company')

        try:
            company_id = int(company_id)
        except ValueError:
            messages.error(request, "Invalid company selected")
            return redirect('select_company')

        if request.user.is_superuser:
            try:
                company = Company.objects.get(id=company_id, is_active=True)

                CompanyMembership.objects.get_or_create(
                    user=request.user,
                    company=company,
                    defaults={
                        'group': 'Admin Staff',
                        'is_active': True
                    }
                )

                request.session['active_company_id'] = company_id
                messages.success(request, f"Switched to {company.name}")

                redirect_url = request.POST.get('next', 'home')
                if redirect_url.startswith('/'):
                    from django.http import HttpResponseRedirect
                    return HttpResponseRedirect(redirect_url)
                else:
                    return redirect(redirect_url)

            except Company.DoesNotExist:
                messages.error(request, "Company not found or inactive")
                return redirect('select_company')

        membership = CompanyMembership.objects.filter(
            user=request.user,
            company_id=company_id,
            is_active=True,
            company__is_active=True
        ).select_related('company').first()

        if membership:
            request.session['active_company_id'] = company_id
            messages.success(request, f"Switched to {membership.company.name}")

            redirect_url = request.POST.get('next', 'home')
            if redirect_url.startswith('/'):
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(redirect_url)
            else:
                return redirect(redirect_url)
        else:
            messages.error(request, "You do not have access to this company")
            return redirect('select_company')


class HomeView(TemplateView):
    template_name = 'vouchers/home.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            active_company_id = request.session.get('active_company_id')
            if not active_company_id:
                print(f"DEBUG: HomeView - No active_company_id, redirecting to select_company")
                return redirect('select_company')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['can_create_voucher'] = user.is_authenticated
        context['is_admin_staff'] = user.is_authenticated and (
            user.groups.filter(name='Admin Staff').exists() or user.is_superuser
        )
        context['is_superuser'] = user.is_superuser

        active_company_id = self.request.session.get('active_company_id')

        if active_company_id:
            context['designations'] = Designation.objects.filter(
                company_id=active_company_id
            ).order_by('name')

            try:
                context['active_company'] = Company.objects.get(id=active_company_id)
                context['company_logo_url'] = context['active_company'].logo.url if context['active_company'].logo else None
            except Company.DoesNotExist:
                context['active_company'] = None
                context['company_logo_url'] = None
        else:
            context['designations'] = Designation.objects.none()
            context['active_company'] = None
            context['company_logo_url'] = None

        if user.is_authenticated:
            context['user_companies'] = CompanyMembership.objects.filter(
                user=user,
                is_active=True,
                company__is_active=True
            ).select_related('company', 'designation').order_by('company__name')

        if user.is_superuser:
            context['all_companies'] = Company.objects.all().order_by('-is_active', 'name')

            all_users = User.objects.select_related('userprofile').prefetch_related(
                'company_memberships__designation',
                'company_memberships__company'
            ).all()

            if active_company_id:
                for u in all_users:
                    u.active_membership = u.company_memberships.filter(
                        company_id=active_company_id,
                        is_active=True
                    ).first()

            context['all_users'] = all_users

        return context


class VoucherListView(LoginRequiredMixin, ListView):
    model = Voucher
    template_name = 'vouchers/voucher_list.html'
    context_object_name = 'vouchers'
    ordering = ['-created_at']

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_view_voucher_list', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        active_company_id = self.request.session.get('active_company_id')
        if not active_company_id:
            return Voucher.objects.none()

        qs = super().get_queryset().filter(company_id=active_company_id)
        qs = qs.select_related('created_by')
        qs = qs.prefetch_related('particulars', 'approvals', 'approvals__approver')
        return qs.annotate(
            approved_count=Count(Case(When(approvals__status='APPROVED', then=1)), output_field=IntegerField()),
            rejected_count=Count(Case(When(approvals__status='REJECTED', then=1)), output_field=IntegerField())
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['can_create_voucher'] = user.is_authenticated
        context['is_admin_staff'] = user.is_authenticated and (
            user.groups.filter(name='Admin Staff').exists() or user.is_superuser
        )

        active_company_id = self.request.session.get('active_company_id')
        if active_company_id:
            context['designations'] = Designation.objects.filter(
                company_id=active_company_id
            ).order_by('name')
        else:
            context['designations'] = Designation.objects.none()

        # Pre-fetch approval levels once for efficiency
        levels = ApprovalLevel.objects.filter(
            company_id=active_company_id,
            is_active=True
        ).order_by('order') if active_company_id else []

        for voucher in context['vouchers']:
            required_snapshot = voucher.required_approvers_snapshot or []
            approved_usernames = set(
                voucher.approvals.filter(status='APPROVED')
                .values_list('approver__username', flat=True)
            )

            if voucher.status == 'PENDING':
                required = set(voucher.required_approvers)
                voucher.pending_approvers = [
                    {'name': name, 'has_approved': name in approved_usernames}
                    for name in required
                ]
            else:
                voucher.pending_approvers = [
                    {'name': name, 'has_approved': True}
                    for name in required_snapshot
                    if name in approved_usernames
                ]

            can_approve = False
            waiting_for_username = None
            first_pending_level = None

            if voucher.status == 'PENDING':
                for lvl in levels:
                    level_users = CompanyMembership.objects.filter(
                        company_id=active_company_id,
                        designation=lvl.designation,
                        group='Admin Staff',
                        is_active=True,
                        user__is_active=True
                    ).values_list('user__id', flat=True)

                    approved_in_level = voucher.approvals.filter(
                        status='APPROVED',
                        approver__id__in=level_users
                    ).count()

                    if approved_in_level < len(level_users):
                        first_pending_level = lvl
                        break

                if first_pending_level:
                    pending_users = CompanyMembership.objects.filter(
                        company_id=active_company_id,
                        designation=first_pending_level.designation,
                        group='Admin Staff',
                        is_active=True,
                        user__is_active=True
                    ).exclude(
                        user__id__in=voucher.approvals.filter(status='APPROVED').values_list('approver__id', flat=True)
                    ).values_list('user__username', flat=True)

                    waiting_for_username = ", ".join(pending_users) if pending_users else "next level"
                else:
                    waiting_for_username = "Approved"
            else:
                waiting_for_username = "Approved"

            # Check if current user can approve this voucher
            if voucher.status == 'PENDING' and (user.groups.filter(name='Admin Staff').exists() or user.is_superuser):
                current_level = None
                for lvl in levels:
                    users_in_level = CompanyMembership.objects.filter(
                        company_id=active_company_id,
                        designation=lvl.designation,
                        group='Admin Staff',
                        is_active=True,
                        user__is_active=True
                    ).values_list('user__username', flat=True)

                    if user.username in users_in_level:
                        current_level = lvl
                        break

                if current_level and first_pending_level == current_level:
                    can_approve = True

            voucher.can_approve = can_approve
            voucher.waiting_for_username = waiting_for_username

        # ── CHANGE 3: Sort vouchers so "needs my approval" float to top ──
        # Vouchers the logged-in user must act on appear first;
        # all other vouchers keep their original order below.
        context['vouchers'] = sorted(
            context['vouchers'],
            key=lambda v: (
                0 if (v.status == 'PENDING' and getattr(v, 'can_approve', False)) else 1
            )
        )

        return context


class VoucherDetailView(LoginRequiredMixin, DetailView):
    model = Voucher
    template_name = 'vouchers/voucher_detail.html'
    context_object_name = 'voucher'

    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
        has_perm, error = check_user_permission(request.user, 'can_view_voucher_detail', active_company_id)
        if not has_perm:
            messages.error(request, error)
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        active_company_id = self.request.session.get('active_company_id')
        if not active_company_id:
            return Voucher.objects.none()

        qs = super().get_queryset().filter(company_id=active_company_id)
        qs = qs.select_related('created_by')
        qs = qs.prefetch_related('particulars', 'approvals__approver')
        return qs.annotate(
            approved_count=Count(Case(When(approvals__status='APPROVED', then=1)), output_field=IntegerField()),
            rejected_count=Count(Case(When(approvals__status='REJECTED', then=1)), output_field=IntegerField())
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        voucher = context['voucher']

        context['can_create_voucher'] = user.is_authenticated
        context['is_admin_staff'] = user.is_authenticated and (
            user.groups.filter(name='Admin Staff').exists() or user.is_superuser
        )

        active_company_id = self.request.session.get('active_company_id')
        context['designations'] = Designation.objects.filter(
            company_id=active_company_id
        ).order_by('name') if active_company_id else Designation.objects.none()

        try:
            context['user_approval'] = voucher.approvals.get(approver=user)
        except VoucherApproval.DoesNotExist:
            context['user_approval'] = None

        total = len(voucher.required_approvers)
        approved = getattr(voucher, 'approved_count', 0) or 0
        context['approval_percentage'] = (approved / total * 100) if total > 0 else 100

        approved_usernames = set(
            voucher.approvals.filter(status='APPROVED')
            .values_list('approver__username', flat=True)
        )

        if voucher.status == 'APPROVED':
            snapshot = voucher.required_approvers_snapshot or []
            context['pending_approvers'] = [
                {'name': name, 'has_approved': True}
                for name in snapshot
                if name in approved_usernames
            ]
        else:
            required = set(voucher.required_approvers)
            context['pending_approvers'] = [
                {'name': name, 'has_approved': name in approved_usernames}
                for name in required
            ]

        if voucher.status == 'PENDING':
            levels = ApprovalLevel.objects.filter(
                company_id=active_company_id,
                is_active=True
            ).select_related('designation').order_by('order')

            level_data = []
            for level in levels:
                level_users = CompanyMembership.objects.filter(
                    company_id=active_company_id,
                    designation=level.designation,
                    group='Admin Staff'
                ).values_list('user__username', flat=True)

                all_approved = any(u in approved_usernames for u in level_users)
                some_approved = any(u in approved_usernames for u in level_users)

                level_data.append({
                    'designation': level.designation,
                    'all_approved': all_approved,
                    'some_approved': some_approved,
                    'is_next': False
                })

            for lvl in level_data:
                if not lvl['all_approved']:
                    lvl['is_next'] = True
                    break

            context['approval_levels'] = level_data
        else:
            snapshot = voucher.required_approvers_snapshot or []
            context['approval_levels'] = [
                {
                    'designation': {'name': name},
                    'all_approved': True,
                    'some_approved': True,
                    'is_next': False
                }
                for name in snapshot
                if name in approved_usernames
            ]

        can_approve = False
        waiting_for_username = None
        first_pending_level = None

        if voucher.status == 'PENDING':
            levels = ApprovalLevel.objects.filter(
                company_id=active_company_id,
                is_active=True
            ).order_by('order')

            for lvl in levels:
                level_users = CompanyMembership.objects.filter(
                    company_id=active_company_id,
                    designation=lvl.designation,
                    group='Admin Staff',
                    is_active=True,
                    user__is_active=True
                ).values_list('user__id', flat=True)

                approved_in_level = voucher.approvals.filter(
                    status='APPROVED',
                    approver__id__in=level_users
                ).count()

                if approved_in_level < len(level_users):
                    first_pending_level = lvl
                    break

            if first_pending_level:
                pending_users = CompanyMembership.objects.filter(
                    company_id=active_company_id,
                    designation=first_pending_level.designation,
                    group='Admin Staff',
                    is_active=True,
                    user__is_active=True
                ).exclude(
                    user__id__in=voucher.approvals.filter(status='APPROVED').values_list('approver__id', flat=True)
                ).values_list('user__username', flat=True)

                waiting_for_username = ", ".join(pending_users) if pending_users else "next level"
            else:
                waiting_for_username = "Approved"
        else:
            waiting_for_username = "Approved"

        if voucher.status == 'PENDING' and (user.groups.filter(name='Admin Staff').exists() or user.is_superuser):
            current_level = None
            for lvl in levels:
                users_in_level = CompanyMembership.objects.filter(
                    company_id=active_company_id,
                    designation=lvl.designation,
                    group='Admin Staff',
                    is_active=True,
                    user__is_active=True
                ).values_list('user__username', flat=True)

                if user.username in users_in_level:
                    current_level = lvl
                    break

            if current_level and first_pending_level == current_level:
                can_approve = True

        context['can_approve'] = can_approve
        context['waiting_for_username'] = waiting_for_username
        context['user_profile'] = user.userprofile if hasattr(user, 'userprofile') else None

        if active_company_id:
            context['user_membership'] = CompanyMembership.objects.filter(
                user=user,
                company_id=active_company_id,
                is_active=True
            ).select_related('designation').first()
        else:
            context['user_membership'] = None

        if active_company_id:
            try:
                context['company'] = Company.objects.get(id=active_company_id)
            except Company.DoesNotExist:
                context['company'] = None
        else:
            context['company'] = None

        return context


# =============================================
# VOUCHER CREATE / EDIT API
# =============================================

class VoucherCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.POST.copy()
        files = request.FILES

        voucher_id = data.get('voucher_id')
        is_edit = bool(voucher_id)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        if is_edit:
            has_perm, error = check_user_permission(request.user, 'can_edit_voucher', active_company_id)
            if not has_perm:
                return Response({'error': error}, status=403)
        else:
            has_perm, error = check_user_permission(request.user, 'can_create_voucher', active_company_id)
            if not has_perm:
                return Response({'error': error}, status=403)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=404)

        try:
            with transaction.atomic():

                # -------------------------------------------------
                # 1. Get or create the voucher
                # -------------------------------------------------
                if is_edit:
                    voucher = Voucher.objects.select_for_update().get(
                        id=voucher_id,
                        company=company
                    )

                    # Only PENDING vouchers can be edited
                    if voucher.status != 'PENDING':
                        return Response(
                            {'error': 'Only pending vouchers can be edited.'},
                            status=400
                        )

                    # ── CHANGE 2: Reset approvals on edit ──
                    # Delete all existing approvals so every approver must
                    # re-approve the updated voucher. This replaces the old
                    # "block edit if approvals exist" behaviour.
                    if voucher.approvals.exists():
                        voucher.approvals.all().delete()

                else:
                    voucher = Voucher(
                        created_by=request.user,
                        company=company
                    )

                # Basic fields
                voucher.voucher_date = data['voucher_date']
                voucher.payment_type = data['payment_type']
                voucher.name_title = data['name_title']
                voucher.pay_to = data['pay_to']

                # Payment-type-specific fields
                if data['payment_type'] == 'CHEQUE':
                    voucher.cheque_number = data.get('cheque_number', '').strip()
                    voucher.cheque_date = data.get('cheque_date') or None
                    voucher.account_details_id = data.get('account_details') or None

                    if not voucher.cheque_number:
                        return Response({'error': 'Cheque number is required.'}, status=400)
                    if not voucher.cheque_date:
                        return Response({'error': 'Cheque date is required.'}, status=400)
                    if not voucher.account_details_id:
                        return Response({'error': 'Account Details is required.'}, status=400)

                elif data['payment_type'] == 'ONLINE':
                    voucher.account_details_id = data.get('account_details') or None
                    voucher.cheque_number = None
                    voucher.cheque_date = None
                    if not voucher.account_details_id:
                        return Response({'error': 'Account Details is required for Online payments.'}, status=400)

                else:
                    voucher.cheque_number = voucher.cheque_date = voucher.account_details = None

                voucher.save()  # generates voucher_number on create

                # -------------------------------------------------
                # 2. Main attachments (multiple, optional)
                # -------------------------------------------------
                main_files = files.getlist('main_attachments')

                if is_edit:
                    if main_files:
                        MainAttachment.objects.filter(voucher=voucher).delete()
                        for f in main_files:
                            MainAttachment.objects.create(voucher=voucher, file=f)
                else:
                    for f in main_files:
                        MainAttachment.objects.create(voucher=voucher, file=f)

                # -------------------------------------------------
                # 3. Cheque attachments
                # -------------------------------------------------
                if data['payment_type'] == 'CHEQUE':
                    cheque_files = files.getlist('cheque_attachments')

                    if is_edit:
                        if cheque_files:
                            ChequeAttachment.objects.filter(voucher=voucher).delete()
                            for f in cheque_files:
                                ChequeAttachment.objects.create(voucher=voucher, file=f)
                    else:
                        if not cheque_files:
                            return Response(
                                {'error': 'At least one cheque attachment is required for Cheque payments.'},
                                status=400
                            )
                        for f in cheque_files:
                            ChequeAttachment.objects.create(voucher=voucher, file=f)

                    if not ChequeAttachment.objects.filter(voucher=voucher).exists():
                        return Response(
                            {'error': 'At least one cheque attachment is required for Cheque payments.'},
                            status=400
                        )
                else:
                    ChequeAttachment.objects.filter(voucher=voucher).delete()

                # -------------------------------------------------
                # 3b. Online attachments (CHANGE 1)
                # Mandatory for NEW online vouchers.
                # On edit: replace only if new files are uploaded,
                # otherwise keep existing files (backward-compatible —
                # old online vouchers without attachments are unaffected).
                # -------------------------------------------------
                if data['payment_type'] == 'ONLINE':
                    online_files = files.getlist('online_attachments')

                    if is_edit:
                        if online_files:
                            # Replace existing online attachments
                            OnlineAttachment.objects.filter(voucher=voucher).delete()
                            for f in online_files:
                                OnlineAttachment.objects.create(voucher=voucher, file=f)
                        # No new files → keep existing (do nothing)
                    else:
                        # CREATE MODE — mandatory for new online vouchers
                        if not online_files:
                            return Response(
                                {'error': 'At least one online attachment is required for Online payments.'},
                                status=400
                            )
                        for f in online_files:
                            OnlineAttachment.objects.create(voucher=voucher, file=f)
                else:
                    # Payment type changed away from ONLINE → clean up stale records
                    OnlineAttachment.objects.filter(voucher=voucher).delete()

                # -------------------------------------------------
                # 4. Particulars + attachments
                # -------------------------------------------------
                i = 0
                existing_particulars = list(voucher.particulars.order_by('id')) if is_edit else []

                while f"particulars[{i}][description]" in data:
                    desc = data[f"particulars[{i}][description]"].strip()
                    amt_str = data[f"particulars[{i}][amount]"].strip()

                    if not desc or not amt_str:
                        i += 1
                        continue

                    try:
                        amount = Decimal(amt_str)
                        if amount <= 0:
                            return Response({f'particular_{i}': 'Amount must be > 0'}, status=400)
                    except InvalidOperation:
                        return Response({f'particular_{i}': 'Invalid amount'}, status=400)

                    new_files = files.getlist(f'particular_attachment_{i}')

                    if i < len(existing_particulars):
                        particular = existing_particulars[i]
                        particular.description = desc
                        particular.amount = amount
                        particular.save()

                        if new_files:
                            for attachment in particular.attachments.all():
                                if attachment.file:
                                    attachment.file.delete(save=False)
                            particular.attachments.all().delete()
                            for f in new_files:
                                ParticularAttachment.objects.create(particular=particular, file=f)
                    else:
                        particular = Particular(voucher=voucher, description=desc, amount=amount)
                        particular.save()

                        if not new_files:
                            return Response(
                                {f'particular_{i}': 'At least one attachment required for new particular'},
                                status=400
                            )
                        for f in new_files:
                            ParticularAttachment.objects.create(particular=particular, file=f)

                    i += 1

                # Delete extra existing particulars
                for j in range(i, len(existing_particulars)):
                    extra = existing_particulars[j]
                    for attachment in extra.attachments.all():
                        if attachment.file:
                            attachment.file.delete(save=False)
                    extra.attachments.all().delete()
                    extra.delete()

                if voucher.particulars.count() == 0:
                    return Response({'error': 'At least one particular is required.'}, status=400)

                for particular in voucher.particulars.all():
                    if not particular.attachments.exists():
                        return Response({
                            'error': f'Particular "{particular.description[:50]}..." requires at least one attachment.'
                        }, status=400)

                action = "updated" if is_edit else "created"

                if not is_edit:
                    try:
                        notify_approvers_new_voucher(voucher, request)
                    except Exception as notify_err:
                        import traceback
                        traceback.print_exc()
                        print(f"⚠️ WhatsApp notification failed (voucher was still created): {notify_err}")

                return Response({
                    'success': True,
                    'message': f'Voucher {voucher.voucher_number} {action} successfully!',
                    'voucher': {
                        'id': voucher.id,
                        'voucher_number': voucher.voucher_number
                    }
                }, status=200 if is_edit else 201)

        except Voucher.DoesNotExist:
            return Response({'error': 'Voucher not found or cannot be edited.'}, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class VoucherNextNumberAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'voucher_number': 'V0001'})
        try:
            company = Company.objects.get(id=active_company_id)
            last = Voucher.objects.filter(company=company).order_by('-id').first()
            if last and last.voucher_number:
                import re
                match = re.search(r'(\d+)$', last.voucher_number)
                if match:
                    num = int(match.group(1)) + 1
                    prefix = last.voucher_number[:match.start()]
                    next_number = f"{prefix}{num:04d}"
                else:
                    next_number = 'V0001'
            else:
                next_number = 'V0001'
        except Company.DoesNotExist:
            next_number = 'V0001'
        return Response({'voucher_number': next_number})


class AccountDetailListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=404)

        accounts = AccountDetail.objects.filter(
            company=company,
            is_active=True
        ).order_by('bank_name')

        serializer = AccountDetailSerializer(accounts, many=True)
        return Response(serializer.data)


class AccountDetailCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=404)

        bank_name = request.data.get('bank_name', '').strip()
        account_number = request.data.get('account_number', '').strip()

        if not bank_name or not account_number:
            return Response({'error': 'Bank name and account number are required'}, status=400)

        if AccountDetail.objects.filter(
            company=company,
            bank_name=bank_name,
            account_number=account_number
        ).exists():
            return Response({
                'error': f'This account already exists in {company.name}'
            }, status=400)

        account = AccountDetail.objects.create(
            company=company,
            bank_name=bank_name,
            account_number=account_number,
            is_active=True,
            created_by=request.user
        )

        return Response({
            'id': account.id,
            'label': str(account),
            'is_active': account.is_active,
            'message': f'Account created successfully in {company.name}'
        }, status=201)


class AccountDetailToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            account = AccountDetail.objects.get(
                pk=pk,
                company_id=active_company_id
            )
            account.is_active = not account.is_active
            account.save()

            status_text = 'enabled' if account.is_active else 'disabled'

            return Response({
                'success': True,
                'message': f'Account {status_text} successfully',
                'is_active': account.is_active
            }, status=200)

        except AccountDetail.DoesNotExist:
            return Response(
                {'error': 'Account not found or does not belong to active company'},
                status=404
            )


class AccountDetailAllAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=404)

        accounts = AccountDetail.objects.filter(
            company=company
        ).order_by('-is_active', 'bank_name')

        data = [{
            'id': acc.id,
            'bank_name': acc.bank_name,
            'account_number': acc.account_number,
            'is_active': acc.is_active,
            'created_at': acc.created_at.strftime('%d %b %Y')
        } for acc in accounts]

        return Response({'accounts': data})


class AccountDetailDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            account = AccountDetail.objects.get(
                pk=pk,
                company_id=active_company_id
            )

            is_used = Voucher.objects.filter(account_details=account).exists()

            if is_used:
                return Response(
                    {'error': 'Cannot delete account. This account is used in one or more vouchers.'},
                    status=400
                )

            account.delete()
            return Response({'message': 'Account deleted successfully'}, status=200)

        except AccountDetail.DoesNotExist:
            return Response(
                {'error': 'Account not found or does not belong to active company'},
                status=404
            )


class VoucherApprovalAPI(AdminStaffRequiredMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        status_choice = request.data.get('status')
        rejection_reason = request.data.get('rejection_reason', '').strip()

        if status_choice not in ['APPROVED', 'REJECTED']:
            return Response({'status': ['Invalid choice.']}, status=status.HTTP_400_BAD_REQUEST)

        if status_choice == 'REJECTED' and not rejection_reason:
            return Response(
                {'rejection_reason': 'Reason is required when rejecting.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    voucher = Voucher.objects.select_for_update(nowait=True).get(pk=pk)

                    active_company_id = request.session.get('active_company_id')
                    if not active_company_id:
                        return Response(
                            {'error': 'No active company selected'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    if request.user.username not in voucher.required_approvers:
                        return Response(
                            {'error': 'You are not authorized to approve this voucher.'},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    if voucher.status != 'PENDING':
                        return Response(
                            {'error': 'This voucher is no longer pending.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    levels = ApprovalLevel.objects.filter(
                        company_id=active_company_id,
                        is_active=True
                    ).order_by('order')

                    approved_usernames = set(
                        voucher.approvals.filter(status='APPROVED')
                        .values_list('approver__username', flat=True)
                    )

                    current_user_level = None
                    for level in levels:
                        users_in_level = CompanyMembership.objects.filter(
                            company_id=active_company_id,
                            designation=level.designation,
                            group='Admin Staff',
                            is_active=True,
                            user__is_active=True
                        ).values_list('user__username', flat=True)

                        if request.user.username in users_in_level:
                            current_user_level = level
                            break

                    if not current_user_level:
                        return Response(
                            {'error': 'Your designation is not in the approval chain.'},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    prev_level = ApprovalLevel.objects.filter(
                        company_id=active_company_id,
                        order__lt=current_user_level.order,
                        is_active=True
                    ).order_by('-order').first()

                    can_approve = True
                    waiting_for = None
                    if prev_level:
                        prev_users = CompanyMembership.objects.filter(
                            company_id=active_company_id,
                            designation=prev_level.designation,
                            group='Admin Staff',
                            is_active=True,
                            user__is_active=True
                        ).values_list('user__username', flat=True)

                        has_any_approval = any(
                            username in approved_usernames for username in prev_users
                        )
                        if not has_any_approval:
                            can_approve = False
                            waiting_for = prev_level.designation.name

                    if not can_approve:
                        return Response({
                            'error': f'Waiting for {waiting_for} to approve first.',
                            'can_approve': False,
                            'waiting_for': waiting_for
                        }, status=status.HTTP_403_FORBIDDEN)

                    approval, created = VoucherApproval.objects.update_or_create(
                        voucher=voucher,
                        approver=request.user,
                        defaults={
                            'status': status_choice,
                            'rejection_reason': rejection_reason if status_choice == 'REJECTED' else None
                        }
                    )

                    voucher.refresh_from_db()
                    voucher._update_status_if_all_approved()

                serializer = VoucherSerializer(voucher, context={'request': request})
                response_data = serializer.data
                response_data['status'] = voucher.status
                response_data['approval'] = {
                    'approver': request.user.username,
                    'approved_at': approval.approved_at.strftime('%d %b %H:%M'),
                    'rejection_reason': approval.rejection_reason
                }
                response_data['can_approve'] = True
                return Response(response_data, status=status.HTTP_200_OK)

            except OperationalError as e:
                if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(0.1 * (2 ** attempt))
                else:
                    return Response(
                        {'error': 'Database is busy. Please try again in a moment.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
            except Voucher.DoesNotExist:
                return Response({'error': 'Voucher not found.'}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response(
                    {'error': f'An error occurred: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(
            {'error': 'Failed to process approval due to database lock.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class DesignationCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=status.HTTP_403_FORBIDDEN)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=status.HTTP_400_BAD_REQUEST)

        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=status.HTTP_404_NOT_FOUND)

        if Designation.objects.filter(company=company, name=name).exists():
            return Response({
                'error': f'Designation "{name}" already exists in {company.name}'
            }, status=status.HTTP_400_BAD_REQUEST)

        designation = Designation.objects.create(
            name=name,
            company=company,
            created_by=request.user
        )

        return Response({
            'message': f"Designation '{designation.name}' created for {company.name}.",
            'id': designation.id
        }, status=status.HTTP_201_CREATED)


class DesignationListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'designations': []})

        designations = Designation.objects.filter(
            company_id=active_company_id
        ).order_by('name')

        data = [{'id': d.id, 'name': d.name} for d in designations]
        return Response({'designations': data})


class ApprovalControlAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=status.HTTP_403_FORBIDDEN)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=status.HTTP_404_NOT_FOUND)

        levels = ApprovalLevel.objects.filter(
            company=company
        ).select_related('designation').order_by('order')

        all_designations = Designation.objects.filter(
            company=company
        ).values('id', 'name').order_by('name')

        return Response({
            'levels': [
                {
                    'id': l.designation.id,
                    'name': l.designation.name,
                    'order': l.order,
                    'is_active': l.is_active
                }
                for l in levels
            ],
            'all_designations': list(all_designations)
        })

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=status.HTTP_403_FORBIDDEN)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=status.HTTP_404_NOT_FOUND)

        levels_data = request.data.get('levels', [])
        if not isinstance(levels_data, list):
            return Response({'error': 'levels must be a list'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            ApprovalLevel.objects.filter(company=company).delete()

            for idx, item in enumerate(levels_data):
                des_id = item.get('id')
                is_active = item.get('is_active', True)
                if not des_id:
                    continue

                try:
                    designation = Designation.objects.get(id=des_id, company=company)
                    ApprovalLevel.objects.create(
                        company=company,
                        designation=designation,
                        order=idx + 1,
                        is_active=is_active,
                        updated_by=request.user
                    )
                except Designation.DoesNotExist:
                    return Response({
                        'error': f'Designation with ID {des_id} not found in {company.name}'
                    }, status=status.HTTP_400_BAD_REQUEST)

            current_required_designation_ids = list(
                ApprovalLevel.objects
                .filter(company=company, is_active=True)
                .order_by('order')
                .values_list('designation_id', flat=True)
            )

            vouchers_to_check = Voucher.objects.filter(
                company=company,
                status__in=['PENDING', 'APPROVED']
            ).select_for_update()

            for voucher in vouchers_to_check:
                approved_count = VoucherApproval.objects.filter(
                    voucher=voucher,
                    status='APPROVED',
                    approver__company_memberships__designation_id__in=current_required_designation_ids,
                    approver__company_memberships__company=company,
                    approver__company_memberships__is_active=True
                ).values('approver__company_memberships__designation_id').distinct().count()

                required_count = len(current_required_designation_ids)

                if required_count > 0 and approved_count >= required_count:
                    voucher.status = 'APPROVED'
                    voucher.save(update_fields=['status'])
                elif required_count == 0:
                    voucher.status = 'APPROVED'
                    voucher.save(update_fields=['status'])

        return Response({
            'message': f'Approval workflow updated for {company.name} and all vouchers recalculated!'
        }, status=status.HTTP_200_OK)


class UserCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        signature = request.FILES.get('signature')

        if not username or not password:
            return Response({'error': 'Username and password are required'}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists'}, status=400)
        if len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters'}, status=400)

        try:
            user = User.objects.create(username=username, password=make_password(password))
            profile = UserProfile.objects.create(user=user)

            if signature:
                profile.signature = signature
            profile.save()

            return Response({
                'message': f'User "{username}" created successfully. Assign to companies in User Assignments.',
                'id': user.id
            }, status=201)

        except Exception as e:
            return Response({'error': str(e)}, status=500)


class VoucherDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=status.HTTP_403_FORBIDDEN)

        voucher = get_object_or_404(Voucher, pk=pk)
        voucher_number = voucher.voucher_number
        voucher.delete()

        return Response({
            'message': f'Voucher {voucher_number} deleted successfully.'
        }, status=status.HTTP_200_OK)


class UserUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'mobile': None})

        membership = CompanyMembership.objects.filter(
            user=request.user,
            company_id=active_company_id,
            is_active=True
        ).first()

        return Response({'mobile': membership.mobile if membership else None})

    def post(self, request):
        signature = request.FILES.get('signature')

        if request.user.is_superuser and request.data.get('user_id'):
            user_id = request.data.get('user_id')
            username = request.data.get('username', '').strip()
            is_active = request.data.get('is_active') in [True, 'true', 'True']

            if not user_id or not username:
                return Response({'error': 'Missing required fields'}, status=400)

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)

            if username != user.username and User.objects.filter(username=username).exists():
                return Response({'error': 'Username already taken'}, status=400)

            user.username = username
            user.is_active = is_active
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)

            if signature:
                profile.signature = signature
            profile.save()

            return Response({'message': 'User updated successfully'}, status=200)

        elif 'mobile' in request.data:
            mobile = request.data.get('mobile', '').strip()
            if not mobile:
                return Response({'error': 'Mobile number is required'}, status=400)

            active_company_id = request.session.get('active_company_id')
            if not active_company_id:
                return Response({'error': 'No active company selected'}, status=400)

            membership = CompanyMembership.objects.filter(
                user=request.user,
                company_id=active_company_id,
                is_active=True
            ).first()

            if not membership:
                return Response({'error': 'No active membership found for this company'}, status=400)

            membership.mobile = mobile
            membership.save(update_fields=['mobile'])

            return Response({
                'message': 'Mobile number updated successfully!',
                'mobile': membership.mobile
            }, status=200)

        else:
            if not signature:
                return Response({'error': 'Please select a signature image'}, status=400)

            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.signature = signature
            profile.save()

            return Response({
                'message': 'Signature updated successfully!',
                'signature_url': profile.signature.url
            }, status=200)






class UserRightsListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=404)

        users = User.objects.filter(
            is_active=True,
            company_memberships__company=company,
            company_memberships__is_active=True
        ).distinct().order_by('username')

        data = []
        for user in users:
            membership = CompanyMembership.objects.filter(
                user=user,
                company=company,
                is_active=True
            ).select_related('designation').first()

            if not membership:
                continue

            perms, created = UserPermission.objects.get_or_create(
                user=user,
                company=company,
                defaults={
                    'can_create_voucher': True,
                    'can_edit_voucher': False,
                    'can_view_voucher_list': True,
                    'can_view_voucher_detail': True,
                    'can_print_voucher': True,
                    'can_create_function': True,
                    'can_edit_function': False,
                    'can_delete_function': False,
                    'can_view_function_list': True,
                    'can_view_function_detail': True,
                    'can_print_function': True,
                    'can_create_holiday': True,
                    'can_edit_holiday': False,
                    'can_delete_holiday': False,
                    'can_view_holiday_list': True,
                    'can_view_holiday_detail': True,
                }
            )

            data.append({
                'id': user.id,
                'username': user.username,
                'group': membership.group,
                'designation': membership.designation.name if membership.designation else 'N/A',
                'permissions': {
                    'can_create_voucher': perms.can_create_voucher,
                    'can_edit_voucher': perms.can_edit_voucher,
                    'can_view_voucher_list': perms.can_view_voucher_list,
                    'can_view_voucher_detail': perms.can_view_voucher_detail,
                    'can_print_voucher': perms.can_print_voucher,
                    'can_create_function': perms.can_create_function,
                    'can_edit_function': perms.can_edit_function,
                    'can_delete_function': perms.can_delete_function,
                    'can_view_function_list': perms.can_view_function_list,
                    'can_view_function_detail': perms.can_view_function_detail,
                    'can_print_function': perms.can_print_function,
                    'can_create_holiday': perms.can_create_holiday,
                    'can_edit_holiday': perms.can_edit_holiday,
                    'can_delete_holiday': perms.can_delete_holiday,
                    'can_view_holiday_list': perms.can_view_holiday_list,
                    'can_view_holiday_detail': perms.can_view_holiday_detail,
                }
            })

        return Response({'users': data})


class UserRightsUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=404)

        user_id = request.data.get('user_id')
        permissions_data = request.data.get('permissions', {})

        if not user_id:
            return Response({'error': 'User ID is required'}, status=400)

        try:
            user = User.objects.get(id=user_id)

            if not CompanyMembership.objects.filter(
                user=user,
                company=company,
                is_active=True
            ).exists():
                return Response({
                    'error': f'{user.username} is not a member of {company.name}'
                }, status=400)

            perms, created = UserPermission.objects.get_or_create(
                user=user,
                company=company,
                defaults={
                    'can_create_voucher': True,
                    'can_edit_voucher': False,
                    'can_view_voucher_list': True,
                    'can_view_voucher_detail': True,
                    'can_print_voucher': True,
                    'can_create_function': True,
                    'can_edit_function': False,
                    'can_delete_function': False,
                    'can_view_function_list': True,
                    'can_view_function_detail': True,
                    'can_print_function': True,
                    'can_create_holiday': True,
                    'can_edit_holiday': False,
                    'can_delete_holiday': False,
                    'can_view_holiday_list': True,
                    'can_view_holiday_detail': True,
                }
            )

            perms.can_create_voucher = permissions_data.get('can_create_voucher', False)
            perms.can_edit_voucher = permissions_data.get('can_edit_voucher', False)
            perms.can_view_voucher_list = permissions_data.get('can_view_voucher_list', False)
            perms.can_view_voucher_detail = permissions_data.get('can_view_voucher_detail', False)
            perms.can_print_voucher = permissions_data.get('can_print_voucher', False)
            perms.can_create_function = permissions_data.get('can_create_function', False)
            perms.can_edit_function = permissions_data.get('can_edit_function', False)
            perms.can_delete_function = permissions_data.get('can_delete_function', False)
            perms.can_view_function_list = permissions_data.get('can_view_function_list', False)
            perms.can_view_function_detail = permissions_data.get('can_view_function_detail', False)
            perms.can_print_function = permissions_data.get('can_print_function', False)
            perms.can_create_holiday = permissions_data.get('can_create_holiday', False)
            perms.can_edit_holiday = permissions_data.get('can_edit_holiday', False)
            perms.can_delete_holiday = permissions_data.get('can_delete_holiday', False)
            perms.can_view_holiday_list = permissions_data.get('can_view_holiday_list', False)
            perms.can_view_holiday_detail = permissions_data.get('can_view_holiday_detail', False)

            perms.updated_by = request.user
            perms.save()

            return Response({
                'success': True,
                'message': f'Permissions updated for {user.username} in {company.name}'
            })

        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class UserRightsBulkUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        updates = request.data.get('updates', [])

        if not updates:
            return Response({'error': 'No updates provided'}, status=400)

        try:
            with transaction.atomic():
                for update in updates:
                    user_id = update.get('user_id')
                    permissions = update.get('permissions', {})

                    if not user_id:
                        continue

                    user = User.objects.get(id=user_id)
                    perms = UserPermission.get_or_create_for_user(user)

                    perms.can_create_voucher = permissions.get('can_create_voucher', False)
                    perms.can_edit_voucher = permissions.get('can_edit_voucher', False)
                    perms.can_create_function = permissions.get('can_create_function', False)
                    perms.can_edit_function = permissions.get('can_edit_function', False)
                    perms.can_delete_function = permissions.get('can_delete_function', False)

                    perms.updated_by = request.user
                    perms.save()

            return Response({
                'success': True,
                'message': f'{len(updates)} user permissions updated successfully'
            })

        except Exception as e:
            return Response({'error': str(e)}, status=500)


class CompanyManagementAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            company = Company.objects.get(id=active_company_id)
            from .serializers import CompanySerializer
            serializer = CompanySerializer(company, context={'request': request})
            return Response(serializer.data)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            company = Company.objects.get(id=active_company_id)
            data = request.POST.copy()
            files = request.FILES

            company.name = data.get('name', company.name).strip()
            company.gst_no = data.get('gst_no', company.gst_no or '').strip()
            company.pan_no = data.get('pan_no', company.pan_no or '').strip()
            company.address = data.get('address', company.address or '').strip()
            company.email = data.get('email', company.email or '').strip()
            company.phone = data.get('phone', company.phone or '').strip()

            if 'logo' in files:
                company.logo = files['logo']

            company.save()

            from .serializers import CompanySerializer
            serializer = CompanySerializer(company, context={'request': request})
            return Response({
                'message': 'Company details saved successfully.',
                'company': serializer.data
            })
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)


# =============================================
# COMPANY MANAGEMENT VIEWS (SUPERUSER ONLY)
# =============================================

class CompanyListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        companies = Company.objects.all().order_by('-is_active', 'name')
        data = [{
            'id': c.id,
            'name': c.name,
            'gst_no': c.gst_no or '',
            'pan_no': c.pan_no or '',
            'address': c.address or '',
            'email': c.email or '',
            'phone': c.phone or '',
            'logo': c.logo.url if c.logo else None,
            'is_active': c.is_active,
            'member_count': c.memberships.filter(is_active=True).count(),
            'voucher_count': c.vouchers.count(),
            'function_count': c.functions.count(),
            'created_at': c.created_at.strftime('%d %b %Y')
        } for c in companies]

        return Response({'companies': data})


class CompanyCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        name = request.POST.get('name', '').strip()
        gst_no = request.POST.get('gst_no', '').strip()
        pan_no = request.POST.get('pan_no', '').strip()
        address = request.POST.get('address', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        logo = request.FILES.get('logo')

        if not name:
            return Response({'error': 'Company name is required'}, status=400)

        if Company.objects.filter(name=name).exists():
            return Response({'error': 'Company with this name already exists'}, status=400)

        try:
            company = Company.objects.create(
                name=name,
                gst_no=gst_no or None,
                pan_no=pan_no or None,
                address=address or None,
                email=email or None,
                phone=phone or None,
                logo=logo,
                is_active=True,
                created_by=request.user
            )

            template_company = Company.objects.exclude(id=company.id).first()
            if template_company:
                template_levels = ApprovalLevel.objects.filter(company=template_company)
                for level in template_levels:
                    ApprovalLevel.objects.create(
                        company=company,
                        designation=level.designation,
                        order=level.order,
                        is_active=level.is_active,
                        updated_by=request.user
                    )

            return Response({
                'success': True,
                'message': f'Company "{name}" created successfully',
                'company': {
                    'id': company.id,
                    'name': company.name
                }
            }, status=201)

        except Exception as e:
            return Response({'error': str(e)}, status=500)


class CompanyUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)

        name = request.POST.get('name', '').strip()
        if name and name != company.name:
            if Company.objects.filter(name=name).exists():
                return Response({'error': 'Company with this name already exists'}, status=400)
            company.name = name

        company.gst_no = request.POST.get('gst_no', '').strip() or None
        company.pan_no = request.POST.get('pan_no', '').strip() or None
        company.address = request.POST.get('address', '').strip() or None
        company.email = request.POST.get('email', '').strip() or None
        company.phone = request.POST.get('phone', '').strip() or None

        if 'logo' in request.FILES:
            company.logo = request.FILES['logo']

        company.save()

        return Response({
            'success': True,
            'message': 'Company updated successfully',
            'company': {
                'id': company.id,
                'name': company.name,
                'logo': company.logo.url if company.logo else None
            }
        })


class CompanyToggleActiveAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)

        company.is_active = not company.is_active
        company.save()

        status_text = 'activated' if company.is_active else 'deactivated'

        return Response({
            'success': True,
            'message': f'Company {status_text} successfully',
            'is_active': company.is_active
        })


class CompanyDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)

        if company.vouchers.exists():
            return Response({
                'error': f'Cannot delete company with {company.vouchers.count()} vouchers. Deactivate instead.'
            }, status=400)

        if company.functions.exists():
            return Response({
                'error': f'Cannot delete company with {company.functions.count()} function bookings. Deactivate instead.'
            }, status=400)

        company_name = company.name
        company.delete()

        return Response({
            'success': True,
            'message': f'Company "{company_name}" deleted successfully'
        })


# =============================================
# USER-COMPANY MEMBERSHIP MANAGEMENT
# =============================================

class UserMembershipListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        users = User.objects.filter(is_active=True).prefetch_related(
            'company_memberships__company',
            'company_memberships__designation',
            'groups'
        ).order_by('username')

        data = []
        for user in users:
            memberships = []
            for membership in user.company_memberships.all():
                memberships.append({
                    'id': membership.id,
                    'company_id': membership.company.id,
                    'company_name': membership.company.name,
                    'group': membership.group,
                    'designation_id': membership.designation.id if membership.designation else None,
                    'designation_name': membership.designation.name if membership.designation else None,
                    'mobile': membership.mobile or '',
                    'is_active': membership.is_active
                })

            data.append({
                'id': user.id,
                'username': user.username,
                'is_superuser': user.is_superuser,
                'memberships': memberships
            })

        companies = Company.objects.filter(is_active=True).order_by('name')
        companies_data = [{'id': c.id, 'name': c.name} for c in companies]

        return Response({
            'users': data,
            'companies': companies_data
        })


class UserMembershipCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        user_id = request.data.get('user_id')
        company_id = request.data.get('company_id')
        group = request.data.get('group')
        designation_id = request.data.get('designation_id')
        mobile = request.data.get('mobile', '').strip()

        if not all([user_id, company_id, group]):
            return Response({'error': 'User, company, and group are required'}, status=400)

        try:
            user = User.objects.get(id=user_id)
            company = Company.objects.get(id=company_id)
        except (User.DoesNotExist, Company.DoesNotExist):
            return Response({'error': 'User or company not found'}, status=404)

        if CompanyMembership.objects.filter(user=user, company=company).exists():
            return Response({'error': f'{user.username} is already assigned to {company.name}'}, status=400)

        designation = None
        if group == 'Admin Staff':
            if not designation_id:
                return Response({'error': 'Designation is required for Admin Staff'}, status=400)
            try:
                designation = Designation.objects.get(id=designation_id)
            except Designation.DoesNotExist:
                return Response({'error': 'Invalid designation'}, status=404)

        try:
            user.groups.clear()
            django_group = Group.objects.get(name=group)
            user.groups.add(django_group)
        except Group.DoesNotExist:
            return Response({'error': f'Group "{group}" does not exist in Django'}, status=400)

        membership = CompanyMembership.objects.create(
            user=user,
            company=company,
            group=group,
            designation=designation,
            mobile=mobile or None,
            is_active=True
        )

        UserPermission.get_or_create_for_user(user, company)

        return Response({
            'success': True,
            'message': f'{user.username} assigned to {company.name}',
            'membership': {
                'id': membership.id,
                'company_name': company.name,
                'group': group,
                'designation': designation.name if designation else None
            }
        }, status=201)


class UserMembershipUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        try:
            membership = CompanyMembership.objects.get(pk=pk)
        except CompanyMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=404)

        group = request.data.get('group')
        designation_id = request.data.get('designation_id')
        mobile = request.data.get('mobile', '').strip()

        if group:
            membership.group = group

            try:
                user = membership.user
                user.groups.clear()
                django_group = Group.objects.get(name=group)
                user.groups.add(django_group)
            except Group.DoesNotExist:
                return Response({'error': f'Group "{group}" does not exist in Django'}, status=400)

            if group == 'Admin Staff':
                if not designation_id:
                    return Response({'error': 'Designation required for Admin Staff'}, status=400)
                try:
                    membership.designation = Designation.objects.get(id=designation_id)
                except Designation.DoesNotExist:
                    return Response({'error': 'Invalid designation'}, status=404)
            else:
                membership.designation = None

        membership.mobile = mobile or None
        membership.save()

        return Response({
            'success': True,
            'message': 'Membership updated successfully'
        })


class UserMembershipToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        try:
            membership = CompanyMembership.objects.get(pk=pk)
        except CompanyMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=404)

        membership.is_active = not membership.is_active
        membership.save()

        action = 'enabled' if membership.is_active else 'disabled'

        return Response({
            'success': True,
            'message': f"Access {action} for {membership.user.username} in {membership.company.name}",
            'is_active': membership.is_active
        })


class UserMembershipDeleteAPI(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        try:
            membership = CompanyMembership.objects.get(pk=pk)
        except CompanyMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=404)

        user_name = membership.user.username
        company_name = membership.company.name

        membership.delete()

        return Response({
            'success': True,
            'message': f'{user_name} removed from {company_name}'
        })


class WhatsAppTestLogAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        from .whatsapp_notification import get_test_logs
        logs = get_test_logs(limit=50)

        return Response({
            'mode': 'TEST',
            'count': len(logs),
            'logs': logs
        })

