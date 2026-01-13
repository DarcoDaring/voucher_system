# voucher_system/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from vouchers.views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # =============================================
    # AUTHENTICATION & COMPANY SELECTION
    # =============================================
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('select-company/', SelectCompanyView.as_view(), name='select_company'),
    path('set-company/', SetCompanyView.as_view(), name='set_company'),
    path('accounts/', include('django.contrib.auth.urls')),  # Password reset, etc.
    
    # =============================================
    # HOME & MAIN VIEWS
    # =============================================
    path('', HomeView.as_view(), name='home'),
    
    # =============================================
    # VOUCHER MANAGEMENT
    # =============================================
    # Views
    path('vouchers/', VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/<int:pk>/', VoucherDetailView.as_view(), name='voucher_detail'),
    
    # APIs
    path('api/vouchers/create/', VoucherCreateAPI.as_view(), name='voucher_create_api'),
    path('api/vouchers/<int:pk>/approve/', VoucherApprovalAPI.as_view(), name='voucher_approval_api'),
    path('api/vouchers/<int:pk>/delete/', VoucherDeleteAPI.as_view(), name='voucher_delete_api'),
    
    # =============================================
    # FUNCTION BOOKING MANAGEMENT
    # =============================================
    # Views
    path('function-details/', FunctionDetailsView.as_view(), name='function'),
    path('function/<int:pk>/', FunctionDetailView.as_view(), name='function_detail'),
    path('function/<int:pk>/print/', FunctionPrintView.as_view(), name='function_print'),
    
    # APIs - CRUD
    path('api/functions/create/', FunctionCreateAPI.as_view(), name='function_create_api'),
    path('api/functions/<int:pk>/update/', FunctionUpdateAPI.as_view(), name='function-update'),
    path('api/functions/<int:pk>/delete/', FunctionDeleteAPI.as_view(), name='function_delete_api'),
    path('api/functions/<int:pk>/confirm/', FunctionConfirmAPI.as_view(), name='function_confirm'),
    path('api/functions/<int:pk>/update-details/', FunctionUpdateDetailsAPI.as_view(), name='function_update_details'),
    
    # APIs - Data Retrieval
    path('api/functions/generate-number/', FunctionGenerateNumberAPI.as_view(), name='function_generate_number'),
    path('api/functions/booked-dates/', FunctionBookedDatesAPI.as_view(), name='function_booked_dates'),
    path('api/functions/by-date/', FunctionListByDateAPI.as_view(), name='function_list_by_date'),
    path('api/functions/by-month/', FunctionListByMonthAPI.as_view(), name='function_list_by_month'),
    path('api/functions/upcoming/', FunctionUpcomingEventsAPI.as_view(), name='function_upcoming_events'),
    path('api/functions/upcoming-count/', FunctionUpcomingCountAPI.as_view(), name='function_upcoming_count'),
    path('api/functions/completed/', FunctionCompletedAPI.as_view(), name='function_completed'),
    path('api/functions/completed-count/', FunctionCompletedCountAPI.as_view(), name='function_completed_count'),
    path('api/functions/pending-by-month/', FunctionPendingByMonthAPI.as_view(), name='function_pending_by_month'),
    path('api/functions/check-time-conflict/', FunctionTimeConflictCheckAPI.as_view(), name='function_time_conflict_check'),
    
    # =============================================
    # COMPANY MANAGEMENT (Superuser)
    # =============================================
    path('api/companies/', CompanyListAPI.as_view(), name='company_list_api'),
    path('api/companies/create/', CompanyCreateAPI.as_view(), name='company_create_api'),
    path('api/companies/<int:pk>/update/', CompanyUpdateAPI.as_view(), name='company_update_api'),
    path('api/companies/<int:pk>/toggle/', CompanyToggleActiveAPI.as_view(), name='company_toggle_api'),
    path('api/companies/<int:pk>/delete/', CompanyDeleteAPI.as_view(), name='company_delete_api'),
    
    # =============================================
    # USER MANAGEMENT (Superuser)
    # =============================================
    path('api/users/create/', UserCreateAPI.as_view(), name='user_create_api'),
    path('api/users/update/', UserUpdateAPI.as_view(), name='user_update_api'),
    
    # User-Company Memberships
    path('api/memberships/', UserMembershipListAPI.as_view(), name='membership_list_api'),
    path('api/memberships/create/', UserMembershipCreateAPI.as_view(), name='membership_create_api'),
    path('api/memberships/<int:pk>/update/', UserMembershipUpdateAPI.as_view(), name='membership_update_api'),
    path('api/memberships/<int:pk>/toggle/', UserMembershipToggleAPI.as_view(), name='membership_toggle'),
    path('api/memberships/<int:pk>/delete/', UserMembershipDeleteAPI.as_view(), name='membership_delete_api'),
    
    # User Rights & Permissions
    path('api/user-rights/', UserRightsListAPI.as_view(), name='user_rights_list'),
    path('api/user-rights/update/', UserRightsUpdateAPI.as_view(), name='user_rights_update'),
    path('api/user-rights/bulk-update/', UserRightsBulkUpdateAPI.as_view(), name='user_rights_bulk_update'),
    
    # =============================================
    # DESIGNATION MANAGEMENT
    # =============================================
    path('api/designations/', DesignationListAPI.as_view(), name='designation_list_api'),
    path('api/designations/create/', DesignationCreateAPI.as_view(), name='designation_create_api'),
    
    # =============================================
    # APPROVAL WORKFLOW CONTROL
    # =============================================
    path('api/approval/control/', ApprovalControlAPI.as_view(), name='approval_control_api'),
    
    # =============================================
    # ACCOUNT DETAILS (Bank Accounts)
    # =============================================
    path('api/accounts/', AccountDetailListAPI.as_view(), name='account_list'),
    path('api/accounts/all/', AccountDetailAllAPI.as_view(), name='account_list_all'),
    path('api/accounts/create/', AccountDetailCreateAPI.as_view(), name='account_create'),
    path('api/accounts/<int:pk>/toggle/', AccountDetailToggleAPI.as_view(), name='account_toggle'),
    path('api/accounts/delete/<int:pk>/', AccountDetailDeleteAPI.as_view(), name='account_delete'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)