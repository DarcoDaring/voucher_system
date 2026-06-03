# voucher_system/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from vouchers.views import (
    HomeView, VoucherListView, VoucherDetailView,
    VoucherCreateAPI, VoucherApprovalAPI,
    DesignationCreateAPI, ApprovalControlAPI,
    UserCreateAPI, UserUpdateAPI, VoucherDeleteAPI,
    AccountDetailListAPI, AccountDetailCreateAPI, AccountDetailDeleteAPI,
    UserRightsListAPI, CompanyManagementAPI, UserRightsUpdateAPI, UserRightsBulkUpdateAPI,
    CustomLoginView, RememberMeLoginView, SelectCompanyView, SetCompanyView,
    CompanyListAPI, CompanyCreateAPI, CompanyUpdateAPI,
    CompanyToggleActiveAPI, CompanyDeleteAPI,
    UserMembershipListAPI, UserMembershipCreateAPI,
    UserMembershipUpdateAPI, UserMembershipDeleteAPI, DesignationListAPI,
    AccountDetailAllAPI, AccountDetailToggleAPI, UserMembershipToggleAPI, VoucherNextNumberAPI, WhatsAppTestLogAPI,
)
from vouchers.function_views import (
    FunctionDetailsView, FunctionBookedDatesAPI, FunctionListByDateAPI,
    FunctionDetailView, FunctionDeleteAPI, FunctionUpdateAPI, FunctionUpcomingEventsAPI,
    FunctionPendingByMonthAPI, FunctionUpcomingCountAPI, FunctionCompletedCountAPI,
    FunctionCompletedAPI, FunctionListByMonthAPI, FunctionUpdateDetailsAPI,
    FunctionTimeConflictCheckAPI, FunctionGenerateNumberAPI, FunctionCreateAPI,
    FunctionConfirmAPI, FunctionPrintView,
)
from vouchers.holiday_views import (
    HolidayView, HolidayDetailView, HolidayCreateAPI,
    HolidayBookedDatesAPI, HolidayListByDateAPI,
    HolidayDeleteAPI, HolidayUpdateAPI, HolidayConfirmAPI, HolidayPrintView,
    VehicleListAPI, VehicleCreateAPI,
    PaymentTypeListAPI, PaymentTypeCreateAPI, PaymentTypeToggleAPI, PaymentTypeUpdateAPI,
    VehicleToggleAPI, VehicleUpdateAPI,
    TripSettlementView, HolidayCompletedListAPI, HolidayCompletedCountAPI,
    TripSettlementGetAPI, TripSettlementSaveAPI,
    BankView, BankListAPI, BankDocumentUploadAPI, BankApproveAPI,
    BankApproverListAPI, BankApproverAddAPI, BankApproverToggleAPI,
    RepairListAPI, RepairCreateAPI, RepairDetailAPI,
    RepairBankSubmitAPI, RepairBankApproveAPI, RepairBankDocumentUploadAPI,
    RepairListForBankAPI, RepairDeleteAPI, RepairUpdateAPI,
    HolidayBankReportAPI, RepairReportAPI,
    HolidayQuickListAPI,
    TripSettlementDeleteAPI, BankSettlementDeleteAPI,
    HolidayReportSummaryAPI,
)
from vouchers.mobile_api import (
    MobileLoginAPI, MobileVoucherListAPI,
    MobileVoucherDetailAPI, MobileVoucherApprovalAPI,
)
from vouchers.mobile_holidays_api import (
    MobileHolidayPermissionsAPI, MobileHolidayStatsAPI,
    MobileHolidayListAPI, MobileHolidayCreateAPI,
    MobileHolidayDetailAPI, MobileHolidayConfirmAPI,
    MobileHolidayUpdateAPI, MobileHolidayDeleteAPI,
    MobileHolidayCompletedListAPI,
    MobileSettlementGetAPI, MobileSettlementSaveAPI,
    MobileBankListAPI, MobileBankUploadAPI, MobileBankApproveAPI,
    MobileVehicleListAPI, MobilePaymentTypeListAPI,
    MobileRepairListAPI, MobileRepairCreateAPI, MobileRepairDetailAPI,
    MobileRepairSubmitBankAPI, MobileRepairBankApproveAPI, MobileRepairDeleteAPI,
)
from vouchers.backup_views import BackupDownloadView, BackupRestoreView
urlpatterns = [
    path('admin/', admin.site.urls),

    # =============================================
    # HOME & MAIN VIEWS
    # =============================================
    path('', HomeView.as_view(), name='home'),

    # =============================================
    # VOUCHER MANAGEMENT
    # =============================================
    path('vouchers/', VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/<int:pk>/', VoucherDetailView.as_view(), name='voucher_detail'),

    # Voucher APIs
    path('api/vouchers/create/', VoucherCreateAPI.as_view(), name='voucher_create_api'),
    path('api/vouchers/<int:pk>/approve/', VoucherApprovalAPI.as_view(), name='voucher_approval_api'),
    path('api/vouchers/<int:pk>/delete/', VoucherDeleteAPI.as_view(), name='voucher_delete_api'),
    path('api/vouchers/next-number/', VoucherNextNumberAPI.as_view(), name='voucher_next_number'),

    # =============================================
    # FUNCTION BOOKING MANAGEMENT
    # =============================================
    path('function-details/', FunctionDetailsView.as_view(), name='function'),
    path('functions/<int:pk>/', FunctionDetailView.as_view(), name='function_detail'),
    path('function/<int:pk>/', FunctionDetailView.as_view(), name='function_detail'),
    path('function/<int:pk>/print/', FunctionPrintView.as_view(), name='function_print'),

    # Function APIs
    path('api/functions/create/', FunctionCreateAPI.as_view(), name='function_create_api'),
    path('api/functions/generate-number/', FunctionGenerateNumberAPI.as_view(), name='function_generate_number'),
    path('api/functions/booked-dates/', FunctionBookedDatesAPI.as_view(), name='function-booked-dates'),
    path('api/functions/booked-dates/', FunctionBookedDatesAPI.as_view(), name='function_booked_dates'),
    path('api/functions/by-date/', FunctionListByDateAPI.as_view(), name='function_list_by_date'),
    path('api/functions/by-month/', FunctionListByMonthAPI.as_view(), name='function_list_by_month'),
    path('api/functions/<int:pk>/update/', FunctionUpdateAPI.as_view(), name='function-update'),
    path('api/functions/<int:pk>/delete/', FunctionDeleteAPI.as_view(), name='function_delete_api'),
    path('api/functions/<int:pk>/confirm/', FunctionConfirmAPI.as_view(), name='function_confirm'),
    path('api/functions/<int:pk>/update-details/', FunctionUpdateDetailsAPI.as_view(), name='function_update_details'),
    path('api/functions/upcoming/', FunctionUpcomingEventsAPI.as_view(), name='function_upcoming_events'),
    path('api/functions/upcoming-count/', FunctionUpcomingCountAPI.as_view()),
    path('api/functions/completed/', FunctionCompletedAPI.as_view()),
    path('api/functions/completed-count/', FunctionCompletedCountAPI.as_view()),
    path('api/functions/pending-by-month/', FunctionPendingByMonthAPI.as_view(), name='function_pending_by_month'),
    path('api/functions/check-time-conflict/', FunctionTimeConflictCheckAPI.as_view(), name='function_time_conflict_check'),

    # =============================================
    # DESIGNATION MANAGEMENT
    # =============================================
    path('api/designations/', DesignationListAPI.as_view(), name='designation_list_api'),
    path('api/designations/by-company/<int:company_id>/', DesignationListAPI.as_view(), name='designation_list_by_company'),
    path('api/designations/create/', DesignationCreateAPI.as_view(), name='designation_create_api'),

    # =============================================
    # APPROVAL WORKFLOW CONTROL
    # =============================================
    path('api/approval/control/', ApprovalControlAPI.as_view(), name='approval_control_api'),

    # =============================================
    # USER MANAGEMENT (Superuser)
    # =============================================
    path('api/users/create/', UserCreateAPI.as_view(), name='user_create_api'),
    path('api/users/update/', UserUpdateAPI.as_view(), name='user_update_api'),

    # User Rights & Permissions
    path('api/user-rights/', UserRightsListAPI.as_view(), name='user_rights_list'),
    path('api/user-rights/update/', UserRightsUpdateAPI.as_view(), name='user_rights_update'),
    path('api/user-rights/bulk-update/', UserRightsBulkUpdateAPI.as_view(), name='user_rights_bulk_update'),

    # =============================================
    # ACCOUNT DETAILS (Bank Accounts)
    # =============================================
    path('api/accounts/list/', AccountDetailListAPI.as_view(), name='account_list'),
    path('api/accounts/', AccountDetailListAPI.as_view(), name='account_list'),
    path('api/accounts/all/', AccountDetailAllAPI.as_view(), name='account_list_all'),
    path('api/accounts/create/', AccountDetailCreateAPI.as_view(), name='account_create'),
    path('api/accounts/<int:pk>/toggle/', AccountDetailToggleAPI.as_view(), name='account_toggle'),
    path('api/accounts/delete/<int:pk>/', AccountDetailDeleteAPI.as_view(), name='account_delete'),

    # =============================================
    # COMPANY MANAGEMENT (Superuser)
    # =============================================
    path('api/company-management/', CompanyManagementAPI.as_view(), name='company_management_api'),
    path('api/companies/', CompanyListAPI.as_view(), name='company_list_api'),
    path('api/companies/create/', CompanyCreateAPI.as_view(), name='company_create_api'),
    path('api/companies/<int:pk>/update/', CompanyUpdateAPI.as_view(), name='company_update_api'),
    path('api/companies/<int:pk>/toggle/', CompanyToggleActiveAPI.as_view(), name='company_toggle_api'),
    path('api/companies/<int:pk>/delete/', CompanyDeleteAPI.as_view(), name='company_delete_api'),

    # =============================================
    # USER-COMPANY MEMBERSHIPS
    # =============================================
    path('api/memberships/', UserMembershipListAPI.as_view(), name='membership_list_api'),
    path('api/memberships/create/', UserMembershipCreateAPI.as_view(), name='membership_create_api'),
    path('api/memberships/<int:pk>/update/', UserMembershipUpdateAPI.as_view(), name='membership_update_api'),
    path('api/memberships/<int:pk>/toggle/', UserMembershipToggleAPI.as_view(), name='membership_toggle'),
    path('api/memberships/<int:pk>/delete/', UserMembershipDeleteAPI.as_view(), name='membership_delete_api'),

    # =============================================
    # AUTHENTICATION & COMPANY SELECTION
    # ⚠️ KEEP THIS ORDER - Django's LoginView first, then custom paths
    # =============================================
    path('accounts/login/', RememberMeLoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # ✅ Custom login/company selection (override with different name)
    
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('select-company/', SelectCompanyView.as_view(), name='select_company'),
    path('set-company/', SetCompanyView.as_view(), name='set_company'),

    path('api/whatsapp/test-logs/', WhatsAppTestLogAPI.as_view(), name='whatsapp_test_logs'),

    # =============================================
    # BACKUP
    # =============================================
    path('backup/download/', BackupDownloadView.as_view(), name='backup_download'),
    path('backup/restore/', BackupRestoreView.as_view(), name='backup_restore'),

    # =============================================
    # HOLIDAY BOOKING MANAGEMENT
    # =============================================
    path('holidays/', HolidayView.as_view(), name='holiday'),
    path('holidays/<int:pk>/', HolidayDetailView.as_view(), name='holiday_detail'),
    path('holidays/<int:pk>/print/', HolidayPrintView.as_view(), name='holiday_print'),

    # Holiday APIs
    path('api/holidays/create/', HolidayCreateAPI.as_view(), name='holiday_create_api'),
    path('api/holidays/booked-dates/', HolidayBookedDatesAPI.as_view(), name='holiday_booked_dates'),
    path('api/holidays/by-date/', HolidayListByDateAPI.as_view(), name='holiday_list_by_date'),
    path('api/holidays/<int:pk>/delete/', HolidayDeleteAPI.as_view(), name='holiday_delete_api'),
    path('api/holidays/<int:pk>/update/', HolidayUpdateAPI.as_view(), name='holiday_update_api'),
    path('api/holidays/<int:pk>/confirm/', HolidayConfirmAPI.as_view(), name='holiday_confirm_api'),

    # Vehicle Master APIs
    path('api/vehicles/', VehicleListAPI.as_view(), name='vehicle_list_api'),
    path('api/vehicles/create/', VehicleCreateAPI.as_view(), name='vehicle_create_api'),
    path('api/vehicles/<int:pk>/toggle/', VehicleToggleAPI.as_view(), name='vehicle_toggle_api'),
    path('api/vehicles/<int:pk>/update/', VehicleUpdateAPI.as_view(), name='vehicle_update_api'),

    # Payment Type Master APIs
    path('api/payment-types/', PaymentTypeListAPI.as_view(), name='payment_type_list_api'),
    path('api/payment-types/create/', PaymentTypeCreateAPI.as_view(), name='payment_type_create_api'),
    path('api/payment-types/<int:pk>/toggle/', PaymentTypeToggleAPI.as_view(), name='payment_type_toggle_api'),
    path('api/payment-types/<int:pk>/update/', PaymentTypeUpdateAPI.as_view(), name='payment_type_update_api'),

    # Trip Settlement
    path('holidays/trip-settlement/', TripSettlementView.as_view(), name='trip_settlement'),
    path('api/holidays/completed/', HolidayCompletedListAPI.as_view(), name='holiday_completed_list'),
    path('api/holidays/completed-count/', HolidayCompletedCountAPI.as_view(), name='holiday_completed_count'),
    path('api/holidays/<int:pk>/settlement/', TripSettlementGetAPI.as_view(), name='holiday_settlement_get'),
    path('api/holidays/<int:pk>/settlement/save/', TripSettlementSaveAPI.as_view(), name='holiday_settlement_save'),

    # Bank Settlement
    path('holidays/bank/', BankView.as_view(), name='bank_settlement'),
    path('api/holidays/bank/list/', BankListAPI.as_view(), name='bank_list_api'),
    path('api/holidays/bank/<int:settlement_pk>/upload/', BankDocumentUploadAPI.as_view(), name='bank_upload_api'),
    path('api/holidays/bank/<int:bank_pk>/approve/', BankApproveAPI.as_view(), name='bank_approve_api'),

    # Bank Approval Master
    path('api/holidays/bank-approvers/', BankApproverListAPI.as_view(), name='bank_approver_list'),
    path('api/holidays/bank-approvers/add/', BankApproverAddAPI.as_view(), name='bank_approver_add'),
    path('api/holidays/bank-approvers/<int:pk>/toggle/', BankApproverToggleAPI.as_view(), name='bank_approver_toggle'),

    # Repair & Maintenance
    path('api/repairs/', RepairListAPI.as_view(), name='repair_list'),
    path('api/repairs/create/', RepairCreateAPI.as_view(), name='repair_create'),
    path('api/repairs/for-bank/', RepairListForBankAPI.as_view(), name='repair_for_bank'),
    path('api/repairs/<int:pk>/', RepairDetailAPI.as_view(), name='repair_detail'),
    path('api/repairs/<int:pk>/submit-to-bank/', RepairBankSubmitAPI.as_view(), name='repair_submit_bank'),
    path('api/repairs/<int:pk>/bank/upload/', RepairBankDocumentUploadAPI.as_view(), name='repair_bank_upload'),
    path('api/repairs/<int:pk>/bank/approve/', RepairBankApproveAPI.as_view(), name='repair_bank_approve'),
    path('api/repairs/<int:pk>/delete/', RepairDeleteAPI.as_view(), name='repair_delete'),
    path('api/repairs/<int:pk>/update/', RepairUpdateAPI.as_view(), name='repair_update'),
    path('api/holidays/report/bank/',    HolidayBankReportAPI.as_view(), name='holiday_bank_report'),
    path('api/repairs/report/',          RepairReportAPI.as_view(),      name='repair_report'),
    path('api/holidays/quick-list/',                   HolidayQuickListAPI.as_view(),       name='holiday_quick_list'),
    path('api/holidays/<int:pk>/settlement/delete/',   TripSettlementDeleteAPI.as_view(),   name='trip_settlement_delete'),
    path('api/holidays/bank/settlement/<int:pk>/delete/', BankSettlementDeleteAPI.as_view(), name='bank_settlement_delete'),
    path('api/holidays/report/summary/',                 HolidayReportSummaryAPI.as_view(), name='holiday_report_summary'),

    # ── MOBILE APP (token-based) ────────────────────────────────────
    path('api/mobile/login/',                    MobileLoginAPI.as_view(),           name='mobile_login'),
    path('api/mobile/vouchers/',                 MobileVoucherListAPI.as_view(),     name='mobile_voucher_list'),
    path('api/mobile/vouchers/<int:pk>/',        MobileVoucherDetailAPI.as_view(),   name='mobile_voucher_detail'),
    path('api/mobile/vouchers/<int:pk>/action/', MobileVoucherApprovalAPI.as_view(), name='mobile_voucher_action'),

    # ── MOBILE HOLIDAYS (token-based) ────────────────────────────────
    path('api/mobile/holidays/permissions/',                        MobileHolidayPermissionsAPI.as_view()),
    path('api/mobile/holidays/stats/',                              MobileHolidayStatsAPI.as_view()),
    path('api/mobile/holidays/completed/',                          MobileHolidayCompletedListAPI.as_view()),
    path('api/mobile/holidays/bank/',                               MobileBankListAPI.as_view()),
    path('api/mobile/holidays/bank/<int:settlement_pk>/upload/',    MobileBankUploadAPI.as_view()),
    path('api/mobile/holidays/bank/<int:bank_pk>/approve/',         MobileBankApproveAPI.as_view()),
    path('api/mobile/holidays/create/',                             MobileHolidayCreateAPI.as_view()),
    path('api/mobile/holidays/<int:pk>/',                           MobileHolidayDetailAPI.as_view()),
    path('api/mobile/holidays/<int:pk>/confirm/',                   MobileHolidayConfirmAPI.as_view()),
    path('api/mobile/holidays/<int:pk>/update/',                    MobileHolidayUpdateAPI.as_view()),
    path('api/mobile/holidays/<int:pk>/delete/',                    MobileHolidayDeleteAPI.as_view()),
    path('api/mobile/holidays/<int:pk>/settlement/',                MobileSettlementGetAPI.as_view()),
    path('api/mobile/holidays/<int:pk>/settlement/save/',           MobileSettlementSaveAPI.as_view()),
    path('api/mobile/holidays/',                                    MobileHolidayListAPI.as_view()),
    path('api/mobile/vehicles/',                                    MobileVehicleListAPI.as_view()),
    path('api/mobile/payment-types/',                               MobilePaymentTypeListAPI.as_view()),
    path('api/mobile/repairs/create/',                              MobileRepairCreateAPI.as_view()),
    path('api/mobile/repairs/<int:pk>/submit-to-bank/',             MobileRepairSubmitBankAPI.as_view()),
    path('api/mobile/repairs/<int:pk>/bank/approve/',               MobileRepairBankApproveAPI.as_view()),
    path('api/mobile/repairs/<int:pk>/delete/',                     MobileRepairDeleteAPI.as_view()),
    path('api/mobile/repairs/<int:pk>/',                            MobileRepairDetailAPI.as_view()),
    path('api/mobile/repairs/',                                     MobileRepairListAPI.as_view()),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)