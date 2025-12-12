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
    CompanyDetailAPI, FunctionDetailsView, FunctionBookedDatesAPI,FunctionListByDateAPI, FunctionDetailView,FunctionDeleteAPI,FunctionUpdateAPI 
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

    # NEW: COMPANY DETAIL API
    path('api/company/', CompanyDetailAPI.as_view(), name='company_detail_api'),

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
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)