from django.contrib import admin
from .models import (
    Voucher, Particular, CompanyMembership, Company,
    FunctionBooking, Designation, UserProfile  # ✅ Add these imports
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
    search_fields = ['function_number', 'function_name', 'contact_numbers']  # ✅ Fixed: contact_numbers not contact_number