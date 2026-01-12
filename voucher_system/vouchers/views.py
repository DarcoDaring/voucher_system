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
    ApprovalLevel, UserProfile, AccountDetail, Company, CompanyMembership,  # ✅ NEW
    MainAttachment, ChequeAttachment, ParticularAttachment, FunctionBooking
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
from .models import UserPermission,CompanyMembership
from django.views import View  # ✅ ADD THIS LINE
from django.contrib.auth import authenticate, login as auth_login, logout

def get_user_designation_for_company(user, company_id):
    """
    Helper function to get a user's designation for a specific company.
    Returns the designation object or None.
    """
    if not company_id:
        return None
    
    membership = CompanyMembership.objects.filter(
        user=user,
        company_id=company_id,
        is_active=True
    ).select_related('designation').first()
    
    return membership.designation if membership else None

def check_user_permission(user, permission_name, company_id=None):
    """
    Check if user has a specific permission IN ACTIVE COMPANY.
    Returns tuple: (has_permission: bool, error_message: str or None)
    """
    if user.is_superuser:
        return True, None
    
    # ✅ If no company_id provided, return False
    if not company_id:
        return False, "No active company selected."
    
    try:
        # ✅ Get permission record for THIS user in THIS company
        perms = UserPermission.objects.filter(
            user=user,
            company_id=company_id
        ).first()
        
        if not perms:
            # Default permissions if record doesn't exist
            if permission_name in ['can_create_voucher', 'can_create_function', 
                                   'can_view_voucher_list', 'can_view_voucher_detail', 'can_print_voucher',
                                   'can_view_function_list', 'can_view_function_detail', 'can_print_function']:
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
            }
            label = permission_labels.get(permission_name, 'perform this action')
            return False, f"You don't have permission to {label}."
        
        return True, None
        
    except Exception as e:
        print(f"Error checking permission: {e}")
        # Default permissions if error occurs
        if permission_name in ['can_create_voucher', 'can_create_function', 
                               'can_view_voucher_list', 'can_view_voucher_detail', 'can_print_voucher',
                               'can_view_function_list', 'can_view_function_detail', 'can_print_function']:
            return True, None
        return False, "You don't have permission to perform this action."
        
    except UserPermission.DoesNotExist:
        # Default permissions if record doesn't exist
        if permission_name in ['can_create_voucher', 'can_create_function', 
                               'can_view_voucher_list', 'can_view_voucher_detail', 'can_print_voucher',
                               'can_view_function_list', 'can_view_function_detail', 'can_print_function']:
            return True, None
        return False, "You don't have permission to perform this action."

def is_function_completed_check(function_date, time_to):
    """
    Helper function to check if a function is completed based on date and time.
    Returns True if current datetime is past the function's end time.
    """
    from django.utils import timezone
    import datetime
    
    # Get current time in configured timezone (Asia/Kolkata)
    now = timezone.localtime(timezone.now())
    
    # Create timezone-aware datetime for function end time
    function_end_datetime = timezone.make_aware(
        datetime.datetime.combine(function_date, time_to)
    )
    
    # Function is completed if current time >= function end time
    return now >= function_end_datetime

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


# === VIEWS ===
# =============================================
# AUTHENTICATION & COMPANY SELECTION VIEWS
# =============================================

class CustomLoginView(View):
    """Custom login view that handles company selection after authentication"""
    
    def get(self, request):
        # If already logged in, redirect to company selection or home
        if request.user.is_authenticated:
            if request.user.is_superuser:
                return redirect('home')  # Superusers go directly to home
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
            
            # ✅ SUPERUSER: Skip company selection entirely
            if user.is_superuser:
                # Auto-select first available company or create one
                company = Company.objects.filter(is_active=True).first()
                
                if not company:
                    # No companies exist - create default
                    company = Company.objects.create(
                        name='Default Company',
                        is_active=True,
                        created_by=user
                    )
                    messages.info(request, f"Created default company: {company.name}")
                
                # Ensure superuser has membership
                membership, created = CompanyMembership.objects.get_or_create(
                    user=user,
                    company=company,
                    defaults={
                        'group': 'Admin Staff',
                        'is_active': True
                    }
                )
                
                # Set active company
                request.session['active_company_id'] = company.id
                messages.success(request, f"Welcome, {user.username}! Currently viewing: {company.name}")
                return redirect('home')
            
            # ✅ REGULAR USER: Must have company assignment
            memberships = CompanyMembership.objects.filter(
                user=user,
                is_active=True,
                company__is_active=True
            ).select_related('company')
            
            if not memberships.exists():
                messages.error(request, "You are not assigned to any company. Please contact your administrator.")
                logout(request)
                return redirect('login')
            
            # If user has only 1 company, auto-select it
            if memberships.count() == 1:
                request.session['active_company_id'] = memberships.first().company.id
                messages.success(request, f"Welcome! Logged in to {memberships.first().company.name}")
                return redirect('home')
            
            # Multiple companies - show selector
            return redirect('select_company')
        else:
            messages.error(request, "Invalid username or password")
            return redirect('login')


class SelectCompanyView(LoginRequiredMixin, View):
    """Show company selection page for users with multiple company access"""
    
    def get(self, request):
        # ✅ Superusers can access all active companies
        if request.user.is_superuser:
            # Get all active companies
            all_companies = Company.objects.filter(is_active=True).order_by('name')
            
            if not all_companies.exists():
                # No companies exist - create default
                company = Company.objects.create(
                    name='Default Company',
                    is_active=True,
                    created_by=request.user
                )
                request.session['active_company_id'] = company.id
                messages.success(request, f"Created and switched to {company.name}")
                return redirect('home')
            
            # Create temporary membership objects for display
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
            
            # If only one company, auto-select
            if len(memberships) == 1:
                request.session['active_company_id'] = memberships[0].company.id
                messages.success(request, f"Switched to {memberships[0].company.name}")
                return redirect('home')
            
            # Show selection page with all companies
            return render(request, 'select_company.html', {
                'memberships': memberships
            })
        
        # ✅ Regular users - only their assigned companies
        memberships = CompanyMembership.objects.filter(
            user=request.user,
            is_active=True,
            company__is_active=True
        ).select_related('company', 'designation')
        
        if not memberships.exists():
            messages.error(request, "You are not assigned to any company. Please contact your administrator.")
            logout(request)
            return redirect('login')
        
        # If only one company, auto-select it
        if memberships.count() == 1:
            request.session['active_company_id'] = memberships.first().company.id
            messages.success(request, f"Switched to {memberships.first().company.name}")
            return redirect('home')
        
        # Show selection page
        return render(request, 'select_company.html', {
            'memberships': memberships
        })

class SetCompanyView(LoginRequiredMixin, View):
    """Handle company selection from dropdown or selection page"""
    
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
        
        # ✅ Superusers can switch to any active company
        if request.user.is_superuser:
            try:
                company = Company.objects.get(id=company_id, is_active=True)
                
                # Ensure membership exists
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
        
        # ✅ Regular users - verify membership
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['can_create_voucher'] = user.is_authenticated
        context['is_admin_staff'] = user.is_authenticated and (
            user.groups.filter(name='Admin Staff').exists() or user.is_superuser
        )
        context['is_superuser'] = user.is_superuser

        # ✅ GET ACTIVE COMPANY FROM SESSION
        active_company_id = self.request.session.get('active_company_id')
        
        # ✅ LOAD DESIGNATIONS FOR ACTIVE COMPANY ONLY
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

        # ✅ GET USER'S COMPANIES FOR SWITCHER
        if user.is_authenticated:
            context['user_companies'] = CompanyMembership.objects.filter(
                user=user,
                is_active=True,
                company__is_active=True
            ).select_related('company', 'designation').order_by('company__name')

        if user.is_superuser:
            # ✅ LOAD ALL COMPANIES FOR MANAGEMENT
            context['all_companies'] = Company.objects.all().order_by('-is_active', 'name')
            
            # Get all users with their company memberships
            all_users = User.objects.select_related('userprofile').prefetch_related(
                'company_memberships__designation',
                'company_memberships__company'
            ).all()
            
            # Attach active company membership for easy template access
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
        # ✅ FILTER BY ACTIVE COMPANY
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
        
        # ✅ FIXED: Only show designations for active company
        active_company_id = self.request.session.get('active_company_id')
        if active_company_id:
            context['designations'] = Designation.objects.filter(
                company_id=active_company_id
            ).order_by('name')
        else:
            context['designations'] = Designation.objects.none()

        # Add waiting_for_username logic for each voucher
        for voucher in context['vouchers']:
            # Get approval data
            required_snapshot = voucher.required_approvers_snapshot or []
            approved_usernames = set(
                voucher.approvals.filter(status='APPROVED')
                .values_list('approver__username', flat=True)
            )

            # For PENDING: show dynamic levels
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

            # Calculate can_approve and waiting_for_username
            can_approve = False
            waiting_for_username = None

            if voucher.status == 'PENDING':
                first_pending_level = None
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

            voucher.can_approve = can_approve
            voucher.waiting_for_username = waiting_for_username

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
        # ✅ FILTER BY ACTIVE COMPANY
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

        if voucher.status == 'PENDING':
            first_pending_level = None
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
        
        # Safely load company details
        if active_company_id:
            try:
                context['company'] = Company.objects.get(id=active_company_id)
            except Company.DoesNotExist:
                context['company'] = None
        else:
            context['company'] = None

        return context
# === FINAL VOUCHER CREATE/EDIT API – FULLY WORKING EDIT MODE ===
class VoucherCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.POST.copy()
        files = request.FILES

        voucher_id = data.get('voucher_id')
        is_edit = bool(voucher_id)

        # ✅ GET ACTIVE COMPANY FIRST
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

        # ✅ GET ACTIVE COMPANY - REQUIRED FOR CREATE & EDIT
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)
        
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
                        created_by=request.user,
                        company=company,  # ✅ VERIFY BELONGS TO ACTIVE COMPANY
                        status='PENDING',
                        approvals__isnull=True  # only editable if no one approved yet
                    )
                else:
                    # ✅ CREATE WITH COMPANY
                    voucher = Voucher(created_by=request.user, company=company)

                # Basic fields
                voucher.voucher_date = data['voucher_date']
                voucher.payment_type = data['payment_type']
                voucher.name_title = data['name_title']
                voucher.pay_to = data['pay_to']

                # Cheque fields
                if data['payment_type'] == 'CHEQUE':
                    voucher.cheque_number = data.get('cheque_number', '').strip()
                    voucher.cheque_date = data.get('cheque_date') or None
                    voucher.account_details_id = data.get('account_details') or None

                    if not voucher.cheque_number:
                        return Response({'error': 'Cheque number is required.'}, status=400)
                    if not voucher.cheque_date:
                        return Response({'error': 'Cheque date is required.'}, status=400)
                    if not voucher.account_details:
                        return Response({'error': 'Account Details is required.'}, status=400)
                else:
                    voucher.cheque_number = voucher.cheque_date = voucher.account_details = None

                voucher.save()  # generates voucher_number on create

                # -------------------------------------------------
                # 2. Main attachments (multiple, optional)
                # -------------------------------------------------
                main_files = files.getlist('main_attachments')

                if is_edit:
                    # EDIT MODE
                    if main_files:
                        # User uploaded new main files → replace all old ones
                        MainAttachment.objects.filter(voucher=voucher).delete()
                        for f in main_files:
                            MainAttachment.objects.create(voucher=voucher, file=f)
                    # If no new files uploaded → keep existing old ones (do nothing)
                else:
                    # CREATE MODE
                    if main_files:
                        # User uploaded main files → create them
                        for f in main_files:
                            MainAttachment.objects.create(voucher=voucher, file=f)
                    # If no files uploaded → that's OK, main attachments are optional
                
                # -------------------------------------------------
                # 3. Cheque attachments – FINAL FIXED VERSION (Create + Edit)
                # -------------------------------------------------
                if data['payment_type'] == 'CHEQUE':
                    cheque_files = files.getlist('cheque_attachments')

                    if is_edit:
                        # EDIT MODE
                        if cheque_files:
                            # User uploaded new cheque images → replace all old ones
                            ChequeAttachment.objects.filter(voucher=voucher).delete()
                            for f in cheque_files:
                                ChequeAttachment.objects.create(voucher=voucher, file=f)
                        # If no new files uploaded → keep old ones (don't delete)
                    else:
                        # CREATE MODE
                        if not cheque_files:
                            return Response({'error': 'At least one cheque attachment is required for Cheque payments.'}, status=400)
                        
                        for f in cheque_files:
                            ChequeAttachment.objects.create(voucher=voucher, file=f)

                    # Final validation: ensure at least one cheque attachment exists
                    if not ChequeAttachment.objects.filter(voucher=voucher).exists():
                        return Response({'error': 'At least one cheque attachment is required for Cheque payments.'}, status=400)

                else:
                    # Not cheque → remove any old cheque attachments
                    ChequeAttachment.objects.filter(voucher=voucher).delete()
                
                # -------------------------------------------------
                # 4. Particulars + attachments (UPDATED FOR PROPER EDIT SUPPORT)
                # -------------------------------------------------
                i = 0
                if is_edit:
                    # Get existing particulars in consistent order
                    existing_particulars = list(voucher.particulars.order_by('id'))
                else:
                    existing_particulars = []

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
                        # UPDATE existing particular
                        particular = existing_particulars[i]
                        particular.description = desc
                        particular.amount = amount
                        particular.save()

                        if new_files:
                            # REPLACE attachments: delete old physical files and DB records
                            for attachment in particular.attachments.all():
                                if attachment.file:
                                    attachment.file.delete(save=False)
                            particular.attachments.all().delete()
                            # Add new ones
                            for f in new_files:
                                ParticularAttachment.objects.create(particular=particular, file=f)
                        # ELSE: Keep existing attachments (no error!)

                    else:
                        # CREATE new particular
                        particular = Particular(voucher=voucher, description=desc, amount=amount)
                        particular.save()

                        if not new_files:
                            return Response(
                                {f'particular_{i}': 'At least one attachment required for new particular'},
                                status=400
                            )
                        # Add attachments
                        for f in new_files:
                            ParticularAttachment.objects.create(particular=particular, file=f)

                    i += 1

                # DELETE extra existing particulars (if frontend sent fewer)
                for j in range(i, len(existing_particulars)):
                    extra = existing_particulars[j]
                    # Delete physical files first
                    for attachment in extra.attachments.all():
                        if attachment.file:
                            attachment.file.delete(save=False)
                    # Then delete DB records
                    extra.attachments.all().delete()
                    extra.delete()

                # Final validation: at least one particular
                if voucher.particulars.count() == 0:
                    return Response({'error': 'At least one particular is required.'}, status=400)
                
                # Optional: Ensure every particular has at least one attachment
                for particular in voucher.particulars.all():
                    if not particular.attachments.exists():
                        return Response({
                            'error': f'Particular "{particular.description[:50]}..." requires at least one attachment.'
                        }, status=400)

                action = "updated" if is_edit else "created"
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
        
class AccountDetailListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)
        
        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=404)
        
        # ✅ FILTER: Only active accounts for voucher creation
        accounts = AccountDetail.objects.filter(
            company=company,
            is_active=True  # ✅ ONLY SHOW ACTIVE ACCOUNTS
        ).order_by('bank_name')
        
        serializer = AccountDetailSerializer(accounts, many=True)
        return Response(serializer.data)
    
class AccountDetailCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        # ✅ GET ACTIVE COMPANY
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

        # ✅ CHECK IF ACCOUNT EXISTS IN THIS COMPANY
        if AccountDetail.objects.filter(
            company=company,
            bank_name=bank_name,
            account_number=account_number
        ).exists():
            return Response({
                'error': f'This account already exists in {company.name}'
            }, status=400)

        # ✅ CREATE ACCOUNT (is_active defaults to True)
        account = AccountDetail.objects.create(
            company=company,
            bank_name=bank_name,
            account_number=account_number,
            is_active=True,  # ✅ NEW ACCOUNTS ARE ACTIVE BY DEFAULT
            created_by=request.user
        )
        
        return Response({
            'id': account.id,
            'label': str(account),
            'is_active': account.is_active,  # ✅ RETURN STATUS
            'message': f'Account created successfully in {company.name}'
        }, status=201)

class AccountDetailToggleAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)

        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            # ✅ VERIFY ACCOUNT BELONGS TO ACTIVE COMPANY
            account = AccountDetail.objects.get(
                pk=pk,
                company_id=active_company_id
            )

            # ✅ TOGGLE STATUS
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
    """Get ALL accounts (active + inactive) for Account Control Modal"""
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
        
        # ✅ GET ALL ACCOUNTS (active + inactive)
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

        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)

        try:
            # ✅ VERIFY ACCOUNT BELONGS TO ACTIVE COMPANY
            account = AccountDetail.objects.get(
                pk=pk,
                company_id=active_company_id
            )

            # ✅ CHECK IF ACCOUNT IS USED IN ANY VOUCHER
            is_used = Voucher.objects.filter(
                account_details=account
            ).exists()

            if is_used:
                return Response(
                    {
                        'error': 'Cannot delete account. This account is used in one or more vouchers.'
                    },
                    status=400
                )

            account.delete()
            return Response(
                {'message': 'Account deleted successfully'},
                status=200
            )

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
                    
                    # ✅ GET ACTIVE COMPANY
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

                    # ✅ FILTER LEVELS BY COMPANY
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
                        # ✅ USE COMPANYMEMBERSHIP INSTEAD OF USERPROFILE
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
                        # ✅ USE COMPANYMEMBERSHIP INSTEAD OF USERPROFILE
                        prev_users = CompanyMembership.objects.filter(
                            company_id=active_company_id,
                            designation=prev_level.designation,
                            group='Admin Staff',
                            is_active=True,
                            user__is_active=True
                        ).values_list('user__username', flat=True)

                        # Only ONE approval needed from previous level
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
                response_data['status'] = voucher.status  # ✅ Return actual voucher status
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
                # ✅ ADD GENERAL EXCEPTION HANDLER
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

        # ✅ GET ACTIVE COMPANY FROM SESSION
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

        # ✅ CHECK IF DESIGNATION EXISTS IN THIS COMPANY
        if Designation.objects.filter(company=company, name=name).exists():
            return Response({
                'error': f'Designation "{name}" already exists in {company.name}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # ✅ CREATE DESIGNATION FOR THIS COMPANY
        designation = Designation.objects.create(
            name=name,
            company=company,
            created_by=request.user
        )

        return Response({
            'message': f"Designation '{designation.name}' created for {company.name}.",
            'id': designation.id
        }, status=status.HTTP_201_CREATED)


# ✅ NEW: API to list designations for active company
class DesignationListAPI(APIView):
    """Get all designations for active company"""
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

        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=status.HTTP_404_NOT_FOUND)

        # ✅ GET APPROVAL LEVELS FOR THIS COMPANY
        levels = ApprovalLevel.objects.filter(
            company=company
        ).select_related('designation').order_by('order')

        # ✅ GET ALL DESIGNATIONS FOR THIS COMPANY
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

        # ✅ GET ACTIVE COMPANY
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
            # ✅ DELETE OLD LEVELS FOR THIS COMPANY ONLY
            ApprovalLevel.objects.filter(company=company).delete()

            # ✅ CREATE NEW LEVELS FOR THIS COMPANY
            for idx, item in enumerate(levels_data):
                des_id = item.get('id')
                is_active = item.get('is_active', True)
                if not des_id:
                    continue
                
                try:
                    # ✅ VERIFY DESIGNATION BELONGS TO THIS COMPANY
                    designation = Designation.objects.get(
                        id=des_id,
                        company=company
                    )
                    
                    ApprovalLevel.objects.create(
                        company=company,  # ✅ SET COMPANY
                        designation=designation,
                        order=idx + 1,
                        is_active=is_active,
                        updated_by=request.user
                    )
                except Designation.DoesNotExist:
                    return Response({
                        'error': f'Designation with ID {des_id} not found in {company.name}'
                    }, status=status.HTTP_400_BAD_REQUEST)

            # ✅ RECALCULATE VOUCHERS FOR THIS COMPANY ONLY
            current_required_designation_ids = list(
                ApprovalLevel.objects
                .filter(company=company, is_active=True)
                .order_by('order')
                .values_list('designation_id', flat=True)
            )

            vouchers_to_check = Voucher.objects.filter(
                company=company,  # ✅ ONLY THIS COMPANY'S VOUCHERS
                status__in=['PENDING', 'APPROVED']
            ).select_for_update()

            for voucher in vouchers_to_check:
                # ✅ Use CompanyMembership instead of UserProfile
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
            # ✅ Create user WITHOUT group - groups assigned via CompanyMembership
            user = User.objects.create(username=username, password=make_password(password))

            # Create basic profile
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

    def post(self, request):
        signature = request.FILES.get('signature')

        # CASE 1: Superuser editing ANY user (from User Control Panel)
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

            # ✅ REMOVED: No longer editing groups here
            # Groups are managed ONLY through CompanyMembership

            profile, _ = UserProfile.objects.get_or_create(user=user)
            
            if signature:
                profile.signature = signature
            profile.save()

            return Response({'message': 'User updated successfully'}, status=200)
            
        # CASE 2: Any logged-in user updating their OWN mobile number
        elif 'mobile' in request.data:
            mobile = request.data.get('mobile', '').strip()
            if not mobile:
                return Response({'error': 'Mobile number is required'}, status=400)
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.mobile = mobile
            profile.save()
            return Response({
                'message': 'Mobile number updated successfully!',
                'mobile': profile.mobile
            }, status=200)

        # CASE 3: Any logged-in user updating ONLY their OWN signature
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

# Add this view to views.py

class FunctionDetailsView(LoginRequiredMixin, TemplateView):
    template_name = 'vouchers/function.html'
    
    def dispatch(self, request, *args, **kwargs):
        active_company_id = request.session.get('active_company_id')
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
    
# Add to views.py

class FunctionGenerateNumberAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'function_number': 'FN0001'})  # Fallback
        
        try:
            company = Company.objects.get(id=active_company_id)
            # ✅ FILTER BY COMPANY
            last_function = FunctionBooking.objects.filter(company=company).order_by('-id').first()
            if last_function and last_function.function_number.startswith('FN'):
                num = int(last_function.function_number[2:]) + 1
                function_number = f'FN{num:04d}'
            else:
                function_number = 'FN0001'
        except Company.DoesNotExist:
            function_number = 'FN0001'
        
        return Response({'function_number': function_number})

#f=create function
class FunctionCreateAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            import json
            
            # ✅ GET ACTIVE COMPANY FIRST
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
            
            # Parse contact numbers (array)
            contact_numbers = json.loads(request.data.get('contact_numbers', '[]'))
            if not contact_numbers:
                return Response({'error': 'At least one contact number is required'}, status=400)
            
            address = request.data.get('address', '').strip()
            
            # Parse menu items (now an object with categories)
            menu_items = json.loads(request.data.get('menu_items', '{}'))
            
            # Location is required during creation
            location = request.data.get('location', '').strip()
            if not location:
                return Response({'error': 'Location is required'}, status=400)
            
            if location not in ['Banquet', 'Restaurant', 'Family Room', 'Outdoor']:
                return Response({'error': 'Invalid location selected'}, status=400)
            
            no_of_pax = request.data.get('no_of_pax')
            rate_per_pax = request.data.get('rate_per_pax', 0)
            gst_option = request.data.get('gst_option', 'INCLUDING')
            hall_rent = request.data.get('hall_rent', 0) or 0
            
            # Parse extra charges (array of objects)
            extra_charges = json.loads(request.data.get('extra_charges', '[]'))
            
            # Get special instructions
            special_instructions = request.data.get('special_instructions', '').strip()
            
            if not all([function_date, time_from, time_to, function_name, address, no_of_pax, rate_per_pax]):
                return Response({'error': 'All required fields must be filled'}, status=400)
            
            # ✅ CREATE FUNCTION WITH COMPANY
            function = FunctionBooking.objects.create(
                company=company,  # ✅ CRITICAL: Assign company here
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
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'booked_dates': []})
        
        # ✅ FILTER BY COMPANY
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
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'functions': []})
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # ✅ FILTER BY COMPANY
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
        # ✅ FILTER BY ACTIVE COMPANY
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
        # ✅ GET ACTIVE COMPANY FIRST
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)
        
        has_perm, error = check_user_permission(request.user, 'can_delete_function', active_company_id)
        if not has_perm:
            return Response({'error': error}, status=403)
    
    # ... rest of the code
        
        try:
            # ✅ FILTER BY COMPANY
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
        """Confirm a function with advance payment, due amount, and food times"""
        if not (request.user.is_superuser or request.user.groups.filter(name='Admin Staff').exists()):
            return Response({'error': 'Permission denied'}, status=403)

        try:
            function = FunctionBooking.objects.get(pk=pk)

            if function.status == 'CONFIRMED':
                return Response({'error': 'Function is already confirmed'}, status=400)

            advance_amount = request.data.get('advance_amount')
            due_amount = request.data.get('due_amount')
            food_pickup_time_str = request.data.get('food_pickup_time')  # <-- raw string
            food_service_time_str = request.data.get('food_service_time')  # <-- raw string

            # Validation for amounts
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

            # === SAFE TIME PARSING (Critical Fix) ===
            from datetime import datetime

            def parse_time(time_str):
                """Convert 'HH:MM' string to datetime.time object or return None"""
                if not time_str or str(time_str).strip() in ('', 'null', 'None'):
                    return None
                try:
                    return datetime.strptime(str(time_str).strip(), '%H:%M').time()
                except ValueError:
                    return None  # Invalid format → treat as None

            function.food_pickup_time = parse_time(food_pickup_time_str)
            function.food_service_time = parse_time(food_service_time_str)

            # Update confirmation fields
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

        except FunctionBooking.DoesNotExist:
            return Response({'error': 'Function not found'}, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)

       
class FunctionUpdateAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        # ✅ GET ACTIVE COMPANY FIRST
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
            
            # Parse menu items (now an object)
            menu_items = json.loads(request.data.get('menu_items', '{}'))
            function.menu_items = menu_items
            
            # Update location
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
            
            # ✅ NEW: Update special instructions
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
        """Get all confirmed upcoming functions (not yet completed based on date + time)"""
        from django.utils import timezone
        import datetime as dt
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'success': True, 'functions': [], 'count': 0})
        
        # Get current datetime
        now = timezone.localtime(timezone.now())
        today_date = now.date()
        current_time = now.time()
        
        # ✅ FILTER BY COMPANY - Get all confirmed functions from today onwards
        functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            status='CONFIRMED',
            function_date__gte=today_date
        ).order_by('function_date', 'time_from')
        
        # Filter out completed functions based on date AND time
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
        
        return Response({
            'success': True,
            'functions': data,
            'count': len(data)
        })

class FunctionPendingByMonthAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'success': True, 'functions': [], 'count': 0})
        
        # First day and last day of the month
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month + 1, 1).date()
        
        # ✅ FILTER BY COMPANY
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
        
        return Response({
            'success': True,
            'functions': data,
            'count': len(data)
        })
    

class FunctionUpcomingCountAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return the total count of confirmed upcoming functions (not yet ended)"""
        from django.utils import timezone
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'count': 0})
        
        now = timezone.localtime(timezone.now())
        today_date = now.date()
        current_time = now.time()
        
        # ✅ FILTER BY COMPANY - Get all confirmed functions from today onwards
        functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            status='CONFIRMED',
            function_date__gte=today_date
        )
        
        # Count only functions that haven't ended yet
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
        """Return count of completed functions (end time has passed)"""
        from django.utils import timezone
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'count': 0})
        
        now = timezone.localtime(timezone.now())
        today_date = now.date()
        current_time = now.time()
        
        # ✅ FILTER BY COMPANY - Get all confirmed functions up to today
        functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            status='CONFIRMED',
            function_date__lte=today_date
        )
        
        # Count only functions where end time has passed
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
        """Get all completed functions (end time has passed)"""
        from django.utils import timezone
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'success': True, 'functions': []})
        
        now = timezone.localtime(timezone.now())
        today_date = now.date()
        current_time = now.time()
        
        # ✅ FILTER BY COMPANY - Get all confirmed functions up to today
        functions = FunctionBooking.objects.filter(
            company_id=active_company_id,
            status='CONFIRMED',
            function_date__lte=today_date
        ).order_by('-function_date', 'time_from')
        
        # Filter to only completed functions (end time passed)
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
        
        return Response({
            'success': True,
            'functions': data
        })
    

class FunctionListByMonthAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all functions for a specific month range"""
        start_date_str = request.GET.get('start')
        end_date_str = request.GET.get('end')
        
        if not start_date_str or not end_date_str:
            return Response({'error': 'start and end date parameters required'}, status=400)
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'functions': []})
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # ✅ FILTER BY COMPANY
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
            
            return Response({
                'success': True,
                'functions': data
            })
            
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
            
            # Update food times
            function.food_pickup_time = parse_time(food_pickup_time_str)
            function.food_service_time = parse_time(food_service_time_str)
            
            # CRITICAL FIX: Only update special_instructions if explicitly sent
            if 'special_instructions' in request.data:
                special_instructions = request.data.get('special_instructions', '').strip()
                function.special_instructions = special_instructions if special_instructions else None
            # Else: do nothing → preserves existing value
            
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
    """Check if there's a time conflict with existing functions"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        function_date = request.data.get('function_date')
        time_from = request.data.get('time_from')
        time_to = request.data.get('time_to')
        function_id = request.data.get('function_id')
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)
        
        if not all([function_date, time_from, time_to]):
            return Response({'error': 'Date and times are required'}, status=400)
        
        try:
            from datetime import datetime, time as dt_time
            
            check_date = datetime.strptime(function_date, '%Y-%m-%d').date()
            check_time_from = datetime.strptime(time_from, '%H:%M').time()
            check_time_to = datetime.strptime(time_to, '%H:%M').time()
            
            # ✅ FILTER BY COMPANY - Get existing functions on the same date
            existing_functions = FunctionBooking.objects.filter(
                company_id=active_company_id,
                function_date=check_date
            )
            
            # Exclude current function if editing
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

class UserRightsListAPI(APIView):
    """Get all users with their current permissions FOR ACTIVE COMPANY"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)
        
        # ✅ GET ACTIVE COMPANY
        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return Response({'error': 'No active company selected'}, status=400)
        
        try:
            company = Company.objects.get(id=active_company_id)
        except Company.DoesNotExist:
            return Response({'error': 'Invalid company'}, status=404)
        
        # ✅ GET USERS WHO HAVE MEMBERSHIP IN THIS COMPANY
        users = User.objects.filter(
            is_active=True,
            company_memberships__company=company,
            company_memberships__is_active=True
        ).distinct().order_by('username')
        
        data = []
        for user in users:
            # ✅ GET USER'S MEMBERSHIP IN THIS COMPANY
            membership = CompanyMembership.objects.filter(
                user=user,
                company=company,
                is_active=True
            ).select_related('designation').first()
            
            if not membership:
                continue  # Skip if no active membership
            
            # ✅ GET OR CREATE PERMISSIONS FOR THIS USER IN THIS COMPANY
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
                }
            )
            
            data.append({
                'id': user.id,
                'username': user.username,
                'group': membership.group,  # ✅ FROM MEMBERSHIP
                'designation': membership.designation.name if membership.designation else 'N/A',  # ✅ FROM MEMBERSHIP
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
                }
            })
        
        return Response({'users': data})


class UserRightsUpdateAPI(APIView):
    """Update permissions for a specific user IN ACTIVE COMPANY"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)
        
        # ✅ GET ACTIVE COMPANY
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
            
            # ✅ VERIFY USER HAS MEMBERSHIP IN THIS COMPANY
            if not CompanyMembership.objects.filter(
                user=user,
                company=company,
                is_active=True
            ).exists():
                return Response({
                    'error': f'{user.username} is not a member of {company.name}'
                }, status=400)
            
            # ✅ GET OR CREATE PERMISSIONS FOR THIS COMPANY
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
                }
            )
            
            # ✅ UPDATE PERMISSIONS
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
    """Update permissions for multiple users at once"""
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
        

# Temporary placeholder - will be replaced with full company management
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
    """Get all companies"""
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
            'voucher_count': c.vouchers.count(),  # ✅ ADDED
            'function_count': c.functions.count(),  # ✅ ADDED
            'created_at': c.created_at.strftime('%d %b %Y')
        } for c in companies]
        
        return Response({'companies': data})


class CompanyCreateAPI(APIView):
    """Create a new company"""
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
            
            # Auto-create approval levels for this company (copy from another company if exists)
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
    """Update company details"""
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
    """Activate or deactivate a company"""
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
    """Delete a company (only if no data exists)"""
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        if not request.user.is_superuser:
            return Response({'error': 'Superuser only'}, status=403)
        
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=404)
        
        # Check if company has any data
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
    """Get all users with their company memberships"""
    permission_classes = [IsAuthenticated]
    
    # Replace UserMembershipListAPI.get method with this:

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
            for membership in user.company_memberships.filter(is_active=True):
                memberships.append({
                    'id': membership.id,
                    'company_id': membership.company.id,
                    'company_name': membership.company.name,
                    'group': membership.group,
                    'designation_id': membership.designation.id if membership.designation else None,  # ✅ ADDED
                    'designation_name': membership.designation.name if membership.designation else None,
                    'mobile': membership.mobile or ''
                })
            
            data.append({
                'id': user.id,
                'username': user.username,
                'is_superuser': user.is_superuser,
                'memberships': memberships
            })
        
        # ✅ ADDED: Include all active companies for the dropdown
        companies = Company.objects.filter(is_active=True).order_by('name')
        companies_data = [{'id': c.id, 'name': c.name} for c in companies]
        
        return Response({
            'users': data,
            'companies': companies_data  # ✅ ADDED
        })


class UserMembershipCreateAPI(APIView):
    """Assign a user to a company"""
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
        
        # Check if membership already exists
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
        
        # ✅ SYNC: Update Django's User.groups to match CompanyMembership
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
        
        # Create default permissions for this user in this company
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
    """Update a user's membership in a company"""
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
            
            # ✅ SYNC: Update Django's User.groups to match CompanyMembership
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


class UserMembershipDeleteAPI(APIView):
    """Remove a user from a company"""
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