# voucher_system/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from vouchers import views
from vouchers.views import (
    HomeView, VoucherListView, VoucherDetailView,
    VoucherCreateAPI, VoucherApprovalAPI,
    DesignationCreateAPI, ApprovalControlAPI,
    UserCreateAPI, UserUpdateAPI, VoucherDeleteAPI,  
    AccountDetailListAPI, AccountDetailCreateAPI, AccountDetailDeleteAPI,
     FunctionDetailsView, FunctionBookedDatesAPI,FunctionListByDateAPI,
    FunctionDetailView,FunctionDeleteAPI,FunctionUpdateAPI,FunctionUpcomingEventsAPI,FunctionPendingByMonthAPI,
    FunctionUpcomingCountAPI,FunctionCompletedCountAPI,FunctionCompletedAPI,FunctionListByMonthAPI,FunctionUpdateDetailsAPI,
    UserRightsListAPI,CompanyManagementAPI, UserRightsUpdateAPI, UserRightsBulkUpdateAPI,FunctionTimeConflictCheckAPI,CustomLoginView, SelectCompanyView, SetCompanyView,
    CompanyListAPI, CompanyCreateAPI, CompanyUpdateAPI, 
    CompanyToggleActiveAPI, CompanyDeleteAPI,
    UserMembershipListAPI, UserMembershipCreateAPI,
    UserMembershipUpdateAPI, UserMembershipDeleteAPI,DesignationListAPI,AccountDetailAllAPI,AccountDetailToggleAPI,UserMembershipToggleAPI,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Home & Vouchers
    path('', HomeView.as_view(), name='home'),
    path('vouchers/', VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/<int:pk>/', VoucherDetailView.as_view(), name='voucher_detail'),



    # API ENDPOINTS
    path('api/vouchers/create/', VoucherCreateAPI.as_view(), name='voucher_create_api'),
    path('api/vouchers/<int:pk>/approve/', VoucherApprovalAPI.as_view(), name='voucher_approval_api'),  # ← Fixed: was 'voucher_approve_api'
    path('api/designations/create/', DesignationCreateAPI.as_view(), name='designation_create_api'),
    path('api/approval/control/', ApprovalControlAPI.as_view(), name='approval_control_api'),  # ← Fixed: consistent path
    path('api/users/create/', UserCreateAPI.as_view(), name='user_create_api'),  # ← NEW: MODAL API
    path('api/users/update/', UserUpdateAPI.as_view(), name='user_update_api'),  # ← NEW: USER CONTROL EDIT API


    # NEW: ACCOUNT DETAIL APIS
    path('api/accounts/list/', AccountDetailListAPI.as_view(), name='account_list'),
    path('api/accounts/create/', AccountDetailCreateAPI.as_view(), name='account_create'),
    path('api/accounts/delete/<int:pk>/', AccountDetailDeleteAPI.as_view(), name='account_delete'),

  

    # AUTH
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('api/vouchers/<int:pk>/delete/', VoucherDeleteAPI.as_view(), name='voucher_delete_api'),
    path('functions/<int:pk>/', FunctionDetailView.as_view(), name='function_detail'),
    path('api/functions/by-date/', FunctionListByDateAPI.as_view(), name='function_list_by_date'),
    path('api/functions/<int:pk>/delete/', FunctionDeleteAPI.as_view(), name='function_delete_api'),
    path('function-details/', views.FunctionDetailsView.as_view(), name='function'),
    path('api/functions/generate-number/', views.FunctionGenerateNumberAPI.as_view(), name='function_generate_number'),
    path('api/functions/create/', views.FunctionCreateAPI.as_view(), name='function_create_api'),
    path('api/functions/booked-dates/', FunctionBookedDatesAPI.as_view(), name='function-booked-dates'),path('api/functions/<int:pk>/confirm/', views.FunctionConfirmAPI.as_view(), name='function_confirm'),
    path('api/functions/<int:pk>/update/', FunctionUpdateAPI.as_view(), name='function-update'),
    path('function/<int:pk>/', views.FunctionDetailView.as_view(), name='function_detail'),
    path('function/<int:pk>/print/', views.FunctionPrintView.as_view(), name='function_print'),
    path('api/functions/upcoming/', FunctionUpcomingEventsAPI.as_view(), name='function_upcoming_events'),
    path('api/functions/pending-by-month/', FunctionPendingByMonthAPI.as_view(), name='function_pending_by_month'),
    path('api/functions/upcoming-count/', FunctionUpcomingCountAPI.as_view()),
    path('api/functions/completed-count/', FunctionCompletedCountAPI.as_view()),
    path('api/functions/completed/', FunctionCompletedAPI.as_view()),
    path('api/functions/by-month/', FunctionListByMonthAPI.as_view(), name='function_list_by_month'),
    path('api/functions/by-date/', FunctionListByDateAPI.as_view(), name='function_list_by_date'),
    path('api/functions/booked-dates/', FunctionBookedDatesAPI.as_view(), name='function_booked_dates'),
    path('api/functions/<int:pk>/update-details/', FunctionUpdateDetailsAPI.as_view(), name='function_update_details'),
    path('api/user-rights/', UserRightsListAPI.as_view(), name='user_rights_list'),
    path('api/user-rights/update/', UserRightsUpdateAPI.as_view(), name='user_rights_update'),
    path('api/user-rights/bulk-update/', UserRightsBulkUpdateAPI.as_view(), name='user_rights_bulk_update'),
    path('api/functions/check-time-conflict/', FunctionTimeConflictCheckAPI.as_view(),name='function_time_conflict_check'),

    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('select-company/', SelectCompanyView.as_view(), name='select_company'),
    path('set-company/', SetCompanyView.as_view(), name='set_company'),
    path('accounts/', include('django.contrib.auth.urls')),  # Keep for password reset, etc.
    path('api/company-management/', CompanyManagementAPI.as_view(), name='company_management_api'),

    # Company Management
    path('api/companies/', CompanyListAPI.as_view(), name='company_list_api'),
    path('api/companies/create/', CompanyCreateAPI.as_view(), name='company_create_api'),
    path('api/companies/<int:pk>/update/', CompanyUpdateAPI.as_view(), name='company_update_api'),
    path('api/companies/<int:pk>/toggle/', CompanyToggleActiveAPI.as_view(), name='company_toggle_api'),
    path('api/companies/<int:pk>/delete/', CompanyDeleteAPI.as_view(), name='company_delete_api'),
    
    # User-Company Memberships
    path('api/memberships/', UserMembershipListAPI.as_view(), name='membership_list_api'),
    path('api/memberships/create/', UserMembershipCreateAPI.as_view(), name='membership_create_api'),
    path('api/memberships/<int:pk>/update/', UserMembershipUpdateAPI.as_view(), name='membership_update_api'),
    path('api/memberships/<int:pk>/delete/', UserMembershipDeleteAPI.as_view(), name='membership_delete_api'),
    path('api/designations/by-company/<int:company_id>/', DesignationListAPI.as_view(), name='designation_list_by_company'),
    path('api/designations/', DesignationListAPI.as_view(), name='designation_list_api'),

    path('api/accounts/', AccountDetailListAPI.as_view(), name='account_list'),  # Only active accounts
    path('api/accounts/all/', AccountDetailAllAPI.as_view(), name='account_list_all'),  # ✅ NEW - All accounts for modal
    path('api/accounts/create/', AccountDetailCreateAPI.as_view(), name='account_create'),
    path('api/accounts/<int:pk>/toggle/', AccountDetailToggleAPI.as_view(), name='account_toggle'),  # ✅ NEW
    path('api/accounts/delete/<int:pk>/', AccountDetailDeleteAPI.as_view(), name='account_delete'),
    path('api/memberships/<int:pk>/toggle/', UserMembershipToggleAPI.as_view(), name='membership_toggle'),

    
    
    
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)