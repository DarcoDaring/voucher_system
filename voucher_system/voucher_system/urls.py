from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from vouchers import views
from vouchers.views import (
    # Pages
    HomeView,
    VoucherListView,
    VoucherDetailView,
    FunctionDetailsView,
    FunctionDetailView,
    FunctionPrintView,

    # Auth / Company selection
    CustomLoginView,
    SelectCompanyView,
    SetCompanyView,

    # Voucher APIs
    VoucherCreateAPI,
    VoucherApprovalAPI,
    VoucherDeleteAPI,

    # Designation / Approval
    DesignationCreateAPI,
    DesignationListAPI,
    ApprovalControlAPI,

    # User APIs
    UserCreateAPI,
    UserUpdateAPI,

    # Account APIs
    AccountDetailListAPI,
    AccountDetailCreateAPI,
    AccountDetailAllAPI,
    AccountDetailToggleAPI,
    AccountDetailDeleteAPI,

    # Function APIs
    FunctionGenerateNumberAPI,
    FunctionCreateAPI,
    FunctionBookedDatesAPI,
    FunctionListByDateAPI,
    FunctionDeleteAPI,
    FunctionUpdateAPI,
    FunctionConfirmAPI,
    FunctionUpcomingEventsAPI,
    FunctionPendingByMonthAPI,
    FunctionUpcomingCountAPI,
    FunctionCompletedCountAPI,
    FunctionCompletedAPI,
    FunctionListByMonthAPI,
    FunctionUpdateDetailsAPI,
    FunctionTimeConflictCheckAPI,

    # User Rights
    UserRightsListAPI,
    UserRightsUpdateAPI,
    UserRightsBulkUpdateAPI,

    # Company Management
    CompanyManagementAPI,
    CompanyListAPI,
    CompanyCreateAPI,
    CompanyUpdateAPI,
    CompanyToggleActiveAPI,
    CompanyDeleteAPI,

    # Memberships
    UserMembershipListAPI,
    UserMembershipCreateAPI,
    UserMembershipUpdateAPI,
    UserMembershipDeleteAPI,
    UserMembershipToggleAPI,
)

urlpatterns = [

    # =====================================================
    # ADMIN
    # =====================================================
    path('admin/', admin.site.urls),

    # =====================================================
    # AUTHENTICATION
    # =====================================================
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),  # password reset, etc.

    # =====================================================
    # COMPANY SELECTION
    # =====================================================
    path('select-company/', SelectCompanyView.as_view(), name='select_company'),
    path('set-company/', SetCompanyView.as_view(), name='set_company'),

    # =====================================================
    # HOME & PAGES
    # =====================================================
    path('', HomeView.as_view(), name='home'),

    # =====================================================
    # VOUCHERS (PAGES)
    # =====================================================
    path('vouchers/', VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/<int:pk>/', VoucherDetailView.as_view(), name='voucher_detail'),

    # =====================================================
    # FUNCTIONS (PAGES)
    # =====================================================
    path('function-details/', FunctionDetailsView.as_view(), name='function'),
    path('functions/<int:pk>/', FunctionDetailView.as_view(), name='function_detail'),
    path('functions/<int:pk>/print/', FunctionPrintView.as_view(), name='function_print'),

    # =====================================================
    # VOUCHER APIs
    # =====================================================
    path('api/vouchers/create/', VoucherCreateAPI.as_view(), name='voucher_create_api'),
    path('api/vouchers/<int:pk>/approve/', VoucherApprovalAPI.as_view(), name='voucher_approval_api'),
    path('api/vouchers/<int:pk>/delete/', VoucherDeleteAPI.as_view(), name='voucher_delete_api'),

    # =====================================================
    # DESIGNATION & APPROVAL APIs
    # =====================================================
    path('api/designations/', DesignationListAPI.as_view(), name='designation_list_api'),
    path('api/designations/by-company/<int:company_id>/', DesignationListAPI.as_view(), name='designation_list_by_company'),
    path('api/designations/create/', DesignationCreateAPI.as_view(), name='designation_create_api'),
    path('api/approval/control/', ApprovalControlAPI.as_view(), name='approval_control_api'),

    # =====================================================
    # USER APIs
    # =====================================================
    path('api/users/create/', UserCreateAPI.as_view(), name='user_create_api'),
    path('api/users/update/', UserUpdateAPI.as_view(), name='user_update_api'),

    # =====================================================
    # ACCOUNT APIs
    # =====================================================
    path('api/accounts/', AccountDetailListAPI.as_view(), name='account_list'),
    path('api/accounts/all/', AccountDetailAllAPI.as_view(), name='account_list_all'),
    path('api/accounts/create/', AccountDetailCreateAPI.as_view(), name='account_create'),
    path('api/accounts/<int:pk>/toggle/', AccountDetailToggleAPI.as_view(), name='account_toggle'),
    path('api/accounts/delete/<int:pk>/', AccountDetailDeleteAPI.as_view(), name='account_delete'),

    # =====================================================
    # FUNCTION APIs
    # =====================================================
    path('api/functions/generate-number/', FunctionGenerateNumberAPI.as_view(), name='function_generate_number'),
    path('api/functions/create/', FunctionCreateAPI.as_view(), name='function_create_api'),
    path('api/functions/booked-dates/', FunctionBookedDatesAPI.as_view(), name='function_booked_dates'),
    path('api/functions/by-date/', FunctionListByDateAPI.as_view(), name='function_list_by_date'),
    path('api/functions/by-month/', FunctionListByMonthAPI.as_view(), name='function_list_by_month'),
    path('api/functions/<int:pk>/update/', FunctionUpdateAPI.as_view(), name='function_update'),
    path('api/functions/<int:pk>/update-details/', FunctionUpdateDetailsAPI.as_view(), name='function_update_details'),
    path('api/functions/<int:pk>/delete/', FunctionDeleteAPI.as_view(), name='function_delete_api'),
    path('api/functions/<int:pk>/confirm/', FunctionConfirmAPI.as_view(), name='function_confirm'),
    path('api/functions/check-time-conflict/', FunctionTimeConflictCheckAPI.as_view(), name='function_time_conflict_check'),

    # =====================================================    
    # Dashboard / stats
    # =====================================================    
    path('api/functions/upcoming/', FunctionUpcomingEventsAPI.as_view(), name='function_upcoming_events'),
    path('api/functions/upcoming-count/', FunctionUpcomingCountAPI.as_view(), name='function_upcoming_count'),
    path('api/functions/completed-count/', FunctionCompletedCountAPI.as_view(), name='function_completed_count'),
    path('api/functions/completed/', FunctionCompletedAPI.as_view(), name='function_completed'),
    path('api/functions/pending-by-month/', FunctionPendingByMonthAPI.as_view(), name='function_pending_by_month'),

    # =====================================================
    # USER RIGHTS APIs
    # =====================================================
    path('api/user-rights/', UserRightsListAPI.as_view(), name='user_rights_list'),
    path('api/user-rights/update/', UserRightsUpdateAPI.as_view(), name='user_rights_update'),
    path('api/user-rights/bulk-update/', UserRightsBulkUpdateAPI.as_view(), name='user_rights_bulk_update'),

    # =====================================================
    # COMPANY MANAGEMENT APIs
    # =====================================================
    path('api/company-management/', CompanyManagementAPI.as_view(), name='company_management_api'),
    path('api/companies/', CompanyListAPI.as_view(), name='company_list_api'),
    path('api/companies/create/', CompanyCreateAPI.as_view(), name='company_create_api'),
    path('api/companies/<int:pk>/update/', CompanyUpdateAPI.as_view(), name='company_update_api'),
    path('api/companies/<int:pk>/toggle/', CompanyToggleActiveAPI.as_view(), name='company_toggle_api'),
    path('api/companies/<int:pk>/delete/', CompanyDeleteAPI.as_view(), name='company_delete_api'),

    # =====================================================
    # USER-COMPANY MEMBERSHIPS
    # =====================================================
    path('api/memberships/', UserMembershipListAPI.as_view(), name='membership_list_api'),
    path('api/memberships/create/', UserMembershipCreateAPI.as_view(), name='membership_create_api'),
    path('api/memberships/<int:pk>/update/', UserMembershipUpdateAPI.as_view(), name='membership_update_api'),
    path('api/memberships/<int:pk>/toggle/', UserMembershipToggleAPI.as_view(), name='membership_toggle_api'),
    path('api/memberships/<int:pk>/delete/', UserMembershipDeleteAPI.as_view(), name='membership_delete_api'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
