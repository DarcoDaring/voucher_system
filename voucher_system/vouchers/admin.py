from django.contrib import admin
from .models import (
    Voucher, Particular, CompanyMembership, Company,
    FunctionBooking, Designation, UserProfile, HolidayBooking,
    RepairMaintenance, RepairItem, Vehicle, PaymentType,
    AccountDetail, ApprovalLevel, WhatsAppConfig, HolidayBankApprover,
)

# ===================================
# DESIGNATION ADMIN (Must be registered FIRST)
# ===================================
@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']  # ✅ REQUIRED for autocomplete
    readonly_fields = ['created_at']


# ===================================
# COMPANY ADMIN
# ===================================
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'gst_no', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'gst_no', 'pan_no']  # ✅ REQUIRED for autocomplete
    readonly_fields = ['created_at', 'updated_at']


# ===================================
# COMPANY MEMBERSHIP ADMIN
# ===================================
@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'group', 'designation', 'is_active']
    list_filter = ['company', 'group', 'is_active']
    search_fields = ['user__username', 'company__name']
    autocomplete_fields = ['user', 'company', 'designation']  # ✅ Now this will work


# ===================================
# VOUCHER ADMIN
# ===================================
@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['voucher_number', 'pay_to', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'payment_type', 'created_by']
    search_fields = ['voucher_number', 'pay_to']
    readonly_fields = ['voucher_number', 'created_by', 'created_at']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        return qs.filter(created_by=request.user)


# ===================================
# PARTICULAR ADMIN
# ===================================
@admin.register(Particular)
class ParticularAdmin(admin.ModelAdmin):
    list_display = ['voucher', 'description', 'amount']
    list_filter = ['voucher']
    search_fields = ['description']


# ===================================
# FUNCTION BOOKING ADMIN
# ===================================
@admin.register(FunctionBooking)
class FunctionBookingAdmin(admin.ModelAdmin):
    list_display = ['function_number', 'function_name', 'function_date', 'time_from', 'time_to', 'no_of_pax', 'created_by']
    list_filter = ['function_date']
    search_fields = ['function_number', 'function_name', 'contact_numbers']


# ===================================
# HOLIDAY BOOKING ADMIN
# ===================================
@admin.register(HolidayBooking)
class HolidayBookingAdmin(admin.ModelAdmin):
    list_display = ['booking_number', 'booked_by', 'trip_date', 'destination', 'no_of_passengers', 'status', 'created_by']
    list_filter = ['status', 'trip_date', 'company']
    search_fields = ['booking_number', 'booked_by', 'destination', 'contact_number']
    readonly_fields = ['booking_number', 'created_at', 'updated_at']


# ===================================
# REPAIR & MAINTENANCE ADMIN
# ===================================
class RepairItemInline(admin.TabularInline):
    model = RepairItem
    extra = 0
    fields = ['name', 'description', 'amount', 'attachment']

@admin.register(RepairMaintenance)
class RepairMaintenanceAdmin(admin.ModelAdmin):
    list_display = ['repair_number', 'vehicle', 'company', 'status', 'total_amount', 'created_by', 'created_at']
    list_filter = ['status', 'company', 'vehicle']
    search_fields = ['repair_number', 'notes']
    readonly_fields = ['repair_number', 'created_at', 'updated_at']
    inlines = [RepairItemInline]


# ===================================
# VEHICLE ADMIN
# ===================================
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['name', 'registration_number', 'company', 'batta_percentage', 'is_active']
    list_filter = ['is_active', 'company']
    search_fields = ['name', 'registration_number']


# ===================================
# PAYMENT TYPE ADMIN
# ===================================
@admin.register(PaymentType)
class PaymentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'is_active', 'created_at']
    list_filter = ['is_active', 'company']
    search_fields = ['name']


# ===================================
# ACCOUNT DETAIL ADMIN
# ===================================
@admin.register(AccountDetail)
class AccountDetailAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'account_number', 'company', 'is_active']
    list_filter = ['is_active', 'company']
    search_fields = ['bank_name', 'account_number']


# ===================================
# APPROVAL LEVEL ADMIN
# ===================================
@admin.register(ApprovalLevel)
class ApprovalLevelAdmin(admin.ModelAdmin):
    list_display = ['company', 'designation', 'order', 'is_active', 'updated_by', 'updated_at']
    list_filter = ['company', 'is_active']


# ===================================
# HOLIDAY BANK APPROVER ADMIN
# ===================================
@admin.register(HolidayBankApprover)
class HolidayBankApproverAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'is_active', 'created_at']
    list_filter = ['is_active', 'company']
    search_fields = ['user__username']


# ===================================
# WHATSAPP CONFIG ADMIN
# ===================================
@admin.register(WhatsAppConfig)
class WhatsAppConfigAdmin(admin.ModelAdmin):
    list_display = ['voucher_enabled', 'function_enabled', 'holiday_enabled', 'updated_at']