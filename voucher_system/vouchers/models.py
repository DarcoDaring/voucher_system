from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
import os
from decimal import Decimal, InvalidOperation

class Designation(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey(
        'Company', 
        on_delete=models.CASCADE, 
        related_name='designations',
        help_text="Company this designation belongs to"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='designations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('company', 'name')
        ordering = ['company__name', 'name']
        verbose_name = "Designation"
        verbose_name_plural = "Designations"

    def __str__(self):
        return f"{self.name} ({self.company.name})"


# =============================================
# COMPANY MODEL (Multi-Company Support)
# =============================================

class Company(models.Model):
    """
    Multi-company support - replaces singleton CompanyDetail.
    Each company has its own vouchers, functions, and approval workflows.
    """
    name = models.CharField(max_length=200, unique=True, help_text="Company Name")
    gst_no = models.CharField(max_length=20, blank=True, null=True, help_text="GST Number")
    pan_no = models.CharField(max_length=15, blank=True, null=True, help_text="PAN Number")
    address = models.TextField(blank=True, null=True, help_text="Full company address")
    email = models.EmailField(blank=True, null=True, help_text="Company email")
    phone = models.CharField(max_length=20, blank=True, null=True, help_text="Company phone")
    logo = models.ImageField(
        upload_to='company/logos/',
        null=True,
        blank=True,
        help_text="Company logo (PNG/JPG, max 2MB)"
    )
    is_active = models.BooleanField(default=True, help_text="Active companies appear in selection")
    enable_vouchers = models.BooleanField(default=True, help_text="Enable Vouchers module for this company")
    enable_functions = models.BooleanField(default=True, help_text="Enable Functions module for this company")
    enable_holidays = models.BooleanField(default=True, help_text="Enable Holidays module for this company")

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='companies_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CompanyMembership(models.Model):
    """
    Links users to companies with role & designation.
    A user can belong to multiple companies with different roles.
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='company_memberships'
    )
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='memberships'
    )
    
    GROUP_CHOICES = (
        ('Admin Staff', 'Admin Staff'),
        ('Accountants', 'Accountants'),
    )
    group = models.CharField(
        max_length=50, 
        choices=GROUP_CHOICES,
        help_text="User's role in this company"
    )
    
    designation = models.ForeignKey(
        'Designation', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Required for Admin Staff"
    )
    
    mobile = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Mobile number for this company"
    )
    
    is_active = models.BooleanField(
        default=True, 
        help_text="Inactive memberships hide the company from user"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'company')
        ordering = ['company__name', 'user__username']
        verbose_name = "Company Membership"
        verbose_name_plural = "Company Memberships"
    
    def __str__(self):
        des = f" - {self.designation.name}" if self.designation else ""
        return f"{self.user.username} @ {self.company.name} ({self.group}{des})"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.group == 'Admin Staff' and not self.designation:
            raise ValidationError("Designation is required for Admin Staff members")


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    signature = models.ImageField(
        upload_to='signatures/',
        null=True,
        blank=True,
        help_text="Upload your digital signature (PNG/JPG, transparent background recommended)"
    )

    def __str__(self):
        return f"{self.user.username} Profile"


class Voucher(models.Model):
    PAYMENT_TYPES = (
        ('CASH', 'Cash'),
        ('CHEQUE', 'Cheque'),
        ('PETTY_CASH', 'Petty Cash'),
        ('ONLINE', 'Online'),
    )
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='vouchers',
        help_text="Company this voucher belongs to"
    )
    voucher_number = models.CharField(max_length=20, blank=True)
    voucher_date = models.DateField()
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    name_title = models.CharField(max_length=5, choices=[('MR', 'Mr.'), ('MRS', 'Mrs.'), ('MS', 'Ms.')])
    pay_to = models.CharField(max_length=200)

    cheque_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Required only for Cheque payments"
    )

    cheque_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date on the cheque - required for Cheque payments"
    )

    account_details = models.ForeignKey(
        'AccountDetail',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Bank account for Cheque/Online payments"
    )

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vouchers')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')],
        default='PENDING'
    )

    required_approvers_snapshot = models.JSONField(
        default=list,
        blank=True,
        help_text="List of usernames required at voucher creation time"
    )

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            with transaction.atomic():
                last_voucher = Voucher.objects.filter(company=self.company).select_for_update().order_by('-id').first()
                if last_voucher and last_voucher.voucher_number.startswith('VCH'):
                    num = int(last_voucher.voucher_number[3:]) + 1
                    self.voucher_number = f'VCH{num:04d}'
                else:
                    self.voucher_number = 'VCH0001'

        if not self.pk:
            super().save(*args, **kwargs)
            self.required_approvers_snapshot = self._get_current_required_approvers()
            self.save(update_fields=['required_approvers_snapshot'])
        else:
            super().save(*args, **kwargs)

    def _get_current_required_approvers(self):
        """Helper: Get current required approvers from active levels."""
        levels = ApprovalLevel.objects.filter(
            company=self.company,
            is_active=True
        ).select_related('designation').order_by('order')
        
        usernames = []
        for level in levels:
            memberships = CompanyMembership.objects.filter(
                company=self.company,
                designation=level.designation,
                group='Admin Staff',
                is_active=True,
                user__is_active=True
            ).values_list('user__username', flat=True).distinct()
            usernames.extend(memberships)
        return usernames

    @property
    def required_approvers(self):
        if self.status in ['APPROVED', 'REJECTED']:
            return self.required_approvers_snapshot or []
        else:
            return self._get_current_required_approvers()

    def _update_status_if_all_approved(self):
        if self.approvals.filter(status='REJECTED').exists():
            self.status = 'REJECTED'
            self.save(update_fields=['status'])
            return

        levels = ApprovalLevel.objects.filter(
            company=self.company,
            is_active=True
        ).order_by('order')
        
        if not levels.exists():
            self.status = 'APPROVED'
            self.save(update_fields=['status'])
            return

        approved_usernames = set(
            self.approvals.filter(status='APPROVED')
                .values_list('approver__username', flat=True)
        )

        for level in levels:
            level_memberships = CompanyMembership.objects.filter(
                company=self.company,
                designation=level.designation,
                group='Admin Staff',
                is_active=True,
                user__is_active=True
            ).values_list('user__username', flat=True)

            if not level_memberships:
                continue

            if not any(username in approved_usernames for username in level_memberships):
                self.status = 'PENDING'
                self.save(update_fields=['status'])
                return

        self.status = 'APPROVED'
        self.save(update_fields=['status'])

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.payment_type == 'CHEQUE':
            if not self.cheque_number:
                raise ValidationError("Cheque number is required for Cheque payments.")
            if not self.cheque_attachments.exists():
                raise ValidationError("At least one cheque attachment is required for Cheque payments.")
            if not self.cheque_date:
                raise ValidationError("Cheque date is required for Cheque payments.")
            if not self.account_details:
                raise ValidationError("Account Details is required for Cheque payments.")
        elif self.payment_type == 'ONLINE':
            if not self.account_details:
                raise ValidationError("Account Details is required for Online payments.")
            self.cheque_number = None
            self.cheque_date = None
        else:
            self.cheque_number = None
            self.cheque_date = None
            self.account_details = None

    class Meta:
        unique_together = ('company', 'voucher_number')
        ordering = ['-created_at']


class Particular(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='particulars')
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.description} - {self.amount}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.attachments.exists():
            raise ValidationError("At least one attachment is required for each particular.")


class VoucherApproval(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[('APPROVED', 'Approved'), ('REJECTED', 'Rejected')])
    approved_at = models.DateTimeField(auto_now_add=True)
    rejection_reason = models.TextField(blank=True, null=True, help_text="Required when status is REJECTED")

    class Meta:
        unique_together = ('voucher', 'approver')

    def __str__(self):
        return f"{self.approver} - {self.status}"


class ApprovalLevel(models.Model):
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='approval_levels',
        help_text="Company this approval level belongs to"
    )
    designation = models.ForeignKey(Designation, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(help_text="Lower number = earlier in approval chain")
    is_active = models.BooleanField(default=True, help_text="Only active levels require approval")
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'designation')
        ordering = ['company', 'order']
        verbose_name = "Approval Level"
        verbose_name_plural = "Approval Levels"

    def __str__(self):
        return f"{self.company.name} - {self.order}. {self.designation.name} ({'Active' if self.is_active else 'Inactive'})"


class AccountDetail(models.Model):
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='accounts',
        help_text="Company this account belongs to"
    )
    bank_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    is_active = models.BooleanField(
        default=True, 
        help_text="Only active accounts appear in voucher creation"
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='account_details')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('company', 'bank_name', 'account_number')
        ordering = ['-is_active', 'bank_name']
    
    def __str__(self):
        status = "✓" if self.is_active else "✗"
        return f"{status} {self.bank_name} / {self.account_number}"


# =============================================
# FILE UPLOAD MODELS
# =============================================

class MainAttachment(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='main_attachments')
    file = models.FileField(upload_to='vouchers/main/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return os.path.basename(self.file.name)


class ChequeAttachment(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='cheque_attachments')
    file = models.FileField(upload_to='vouchers/cheques/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return os.path.basename(self.file.name)


class ParticularAttachment(models.Model):
    particular = models.ForeignKey(Particular, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='vouchers/particulars/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return os.path.basename(self.file.name)


class OnlineAttachment(models.Model):
    """
    Attachments for Online payment vouchers.

    Mandatory for NEW online vouchers created after this model was added.
    Existing online vouchers (created before this feature) may have zero
    records in this table — that is intentional and harmless; the views
    never enforce the presence check on existing vouchers.
    """
    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name='online_attachments'
    )
    file = models.FileField(upload_to='vouchers/online/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return os.path.basename(self.file.name)


class UserPermission(models.Model):
    """
    Granular permissions for each user PER COMPANY.
    """
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='user_permissions',
        help_text="Company these permissions apply to"
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permissions')
    
    # Voucher Permissions
    can_create_voucher = models.BooleanField(default=True, help_text="User can create new vouchers")
    can_edit_voucher = models.BooleanField(default=False, help_text="User can edit existing vouchers")
    can_view_voucher_list = models.BooleanField(default=True, help_text="User can view voucher list page")
    can_view_voucher_detail = models.BooleanField(default=True, help_text="User can view individual voucher details")
    can_print_voucher = models.BooleanField(default=True, help_text="User can print vouchers")
    
    # Function Permissions
    can_create_function = models.BooleanField(default=True, help_text="User can create new function bookings")
    can_edit_function = models.BooleanField(default=False, help_text="User can edit existing function bookings")
    can_delete_function = models.BooleanField(default=False, help_text="User can delete function bookings")
    can_view_function_list = models.BooleanField(default=True, help_text="User can view function calendar/list page")
    can_view_function_detail = models.BooleanField(default=True, help_text="User can view individual function details")
    can_print_function = models.BooleanField(default=True, help_text="User can print function prospectus")

    # Holiday Permissions
    can_create_holiday = models.BooleanField(default=True, help_text="User can create holiday bookings")
    can_edit_holiday = models.BooleanField(default=False, help_text="User can edit holiday bookings")
    can_delete_holiday = models.BooleanField(default=False, help_text="User can delete holiday bookings")
    can_view_holiday_list = models.BooleanField(default=True, help_text="User can view holiday calendar")
    can_view_holiday_detail = models.BooleanField(default=True, help_text="User can view holiday booking details")

    # Metadata
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='permission_updates')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'company')
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"
    
    def __str__(self):
        return f"Permissions for {self.user.username} @ {self.company.name}"
    
    @classmethod
    def get_or_create_for_user(cls, user, company):
        """Get or create permissions for a user in a specific company."""
        obj, created = cls.objects.get_or_create(
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
        return obj


# =============================================
# FUNCTION BOOKING
# =============================================

class FunctionBooking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Confirmation'),
        ('CONFIRMED', 'Function Confirmed'),
        ('CANCELLED', 'Cancelled'),
    )
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='functions',
        help_text="Company this function belongs to"
    )
    
    GST_CHOICES = (
        ('INCLUDING', 'Including GST'),
        ('EXCLUDING', 'Excluding GST'),
    )
    
    LOCATION_CHOICES = (
        ('Banquet', 'Banquet'),
        ('Restaurant', 'Restaurant'),
        ('Family Room', 'Family Room'),
        ('Outdoor', 'Outdoor'),
    )
    
    function_number = models.CharField(max_length=20, blank=True)
    function_date = models.DateField()
    time_from = models.TimeField()
    time_to = models.TimeField()
    function_name = models.CharField(max_length=200)
    booked_by = models.CharField(max_length=200, help_text="Name of person/company who booked")
    contact_numbers = models.JSONField(default=list, help_text="List of contact numbers")
    address = models.TextField(max_length=500)
    menu_items = models.JSONField(
        default=dict, 
        help_text="Menu items categorized: {welcome_drink, starters, main_course, desserts}"
    )
    no_of_pax = models.IntegerField()
    rate_per_pax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_option = models.CharField(max_length=20, choices=GST_CHOICES, default='INCLUDING')
    hall_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    location = models.CharField(
        max_length=50, 
        choices=LOCATION_CHOICES, 
        help_text="Location where the function will be held"
    )
    extra_charges = models.JSONField(default=list, help_text="List of extra charges with description and rate")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Remaining amount to be paid (Total - Advance)"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING',
        help_text="Function confirmation status"
    )
    advance_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Advance payment amount"
    )
    food_pickup_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Time when food should be picked up"
    )
    food_service_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Time when food service should begin"
    )
    special_instructions = models.TextField(
        blank=True,
        null=True,
        help_text="Special instructions or notes for the function"
    )
    
    confirmed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='confirmed_functions',
        help_text="User who confirmed the function"
    )
    confirmed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp when function was confirmed"
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='function_bookings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('company', 'function_number')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.function_number} - {self.function_name}"
    
    def save(self, *args, **kwargs):
        if not self.function_number:
            with transaction.atomic():
                last_function = FunctionBooking.objects.filter(company=self.company).select_for_update().order_by('-id').first()
                if last_function and last_function.function_number.startswith('FN'):
                    num = int(last_function.function_number[2:]) + 1
                    self.function_number = f'FN{num:04d}'
                else:
                    self.function_number = 'FN0001'

        self.calculate_total_amount()
        total = Decimal(self.total_amount or 0)
        advance = Decimal(self.advance_amount or 0)
        self.due_amount = total - advance

        if self.due_amount < 0:
            self.due_amount = Decimal('0.00')

        super().save(*args, **kwargs)
    
    def calculate_total_amount(self):
        """Calculate total amount based on pax, rate, GST, hall rent and extra charges."""
        base_amount = Decimal(self.no_of_pax) * Decimal(self.rate_per_pax)
        
        if self.gst_option == 'INCLUDING':
            amount_with_gst = base_amount + ((base_amount * 5) / 100)
        else:
            amount_with_gst = base_amount 
        
        hall_rent = Decimal(self.hall_rent or 0)
        extra_total = sum(Decimal(charge.get('rate', 0)) for charge in self.extra_charges)
        
        self.total_amount = amount_with_gst + hall_rent + extra_total
    
    @property
    def is_function_completed(self):
        """
        Check if function is completed based on date and time.
        Uses timezone-aware datetime comparison.
        """
        from django.utils import timezone
        import datetime

        now = timezone.localtime(timezone.now())
        function_end_datetime = timezone.make_aware(
            datetime.datetime.combine(self.function_date, self.time_to)
        )
        return now >= function_end_datetime


# =============================================
# EXTERNAL API KEY (for third-party / local-network apps)
# =============================================

class ExternalApiKey(models.Model):
    """
    A company-scoped API key for external / local-network applications.
    No user login required — the key itself identifies the company.
    Create keys via Django admin and share with the consuming app.
    """
    name = models.CharField(max_length=100, help_text="Label for this key, e.g. 'Kitchen Display System'")
    key = models.CharField(max_length=64, unique=True, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='api_keys',
        help_text="Only data belonging to this company will be returned"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            import secrets
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    class Meta:
        verbose_name = "External API Key"
        verbose_name_plural = "External API Keys"


# =============================================
# VEHICLE MASTER
# =============================================

class Vehicle(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='vehicles')
    name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50)
    batta_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='vehicles_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'registration_number')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.registration_number})"


# =============================================
# PAYMENT TYPE MASTER
# =============================================

class PaymentType(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payment_types')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='payment_types_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


# =============================================
# HOLIDAY BOOKING
# =============================================

class HolidayBooking(models.Model):
    STATUS_CHOICES = (
        ('PENDING',   'Pending'),
        ('CONFIRMED',  'Confirmed'),
        ('COMPLETED',  'Completed'),
        ('CANCELLED',  'Cancelled'),
    )
    AC_TYPE_CHOICES = (
        ('AC', 'AC'),
        ('NON_AC', 'Non-AC'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='holidays')
    booking_number = models.CharField(max_length=20, blank=True)
    trip_date = models.DateField()
    purpose_of_booking = models.CharField(max_length=300, blank=True, null=True)
    booked_by = models.CharField(max_length=200)
    contact_number = models.CharField(max_length=15)
    second_contact_number = models.CharField(max_length=15, blank=True, null=True)
    departure_location = models.CharField(max_length=200)
    destination = models.CharField(max_length=500)
    departure_time = models.TimeField()
    return_date = models.DateField(null=True, blank=True)
    return_time = models.TimeField(null=True, blank=True)
    payment_type_label = models.CharField(max_length=100, blank=True, null=True)
    max_km = models.IntegerField(null=True, blank=True)
    extra_km_charge = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    no_of_passengers = models.IntegerField()
    booked_vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings'
    )
    ac_type = models.CharField(max_length=10, choices=AC_TYPE_CHOICES, default='NON_AC')
    total_rent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    service_charge = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    special_instructions = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='holiday_bookings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Legacy field kept for existing records
    fare_per_person = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('company', 'booking_number')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.booking_number} - {self.destination}"

    def save(self, *args, **kwargs):
        if not self.booking_number:
            last = HolidayBooking.objects.filter(company=self.company).order_by('-id').first()
            if last and last.booking_number.startswith('HOL-'):
                num = int(last.booking_number[4:]) + 1
                self.booking_number = f'HOL-{num}'
            else:
                self.booking_number = 'HOL-1'
        total_rent = Decimal(self.total_rent or 0)
        service_charge = Decimal(self.service_charge or 0)
        self.total_amount = total_rent + service_charge
        advance = Decimal(self.advance_amount or 0)
        self.balance_amount = max(Decimal('0.00'), self.total_amount - advance)
        super().save(*args, **kwargs)


# =============================================
# TRIP SETTLEMENT
# =============================================

class TripSettlement(models.Model):
    booking = models.OneToOneField(HolidayBooking, on_delete=models.CASCADE, related_name='settlement')
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_rent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    batta_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    batta_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    extra_rent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    diesel_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    diesel_bill = models.FileField(upload_to='settlement/diesel/', null=True, blank=True)
    cleaning_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grease_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grease_bill = models.FileField(upload_to='settlement/grease/', null=True, blank=True)
    net_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='settlements_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settlement – {self.booking.booking_number}"


class TripSettlementCharge(models.Model):
    settlement = models.ForeignKey(TripSettlement, on_delete=models.CASCADE, related_name='custom_charges')
    name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    attachment = models.FileField(upload_to='settlement/custom/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}: {self.amount}"


# =============================================
# BANK SETTLEMENT
# =============================================

class BankSettlement(models.Model):
    STATUS_PENDING  = 'PENDING_APPROVAL'
    STATUS_APPROVED = 'APPROVED'
    STATUS_CHOICES  = (
        (STATUS_PENDING,  'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
    )

    settlement    = models.OneToOneField(TripSettlement, on_delete=models.CASCADE, related_name='bank')
    bank_document = models.FileField(upload_to='settlement/bank/')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    approved_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_approvals')
    approved_at   = models.DateTimeField(null=True, blank=True)
    submitted_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bank_submissions')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bank – {self.settlement.booking.booking_number}"


# =============================================
# REPAIR & MAINTENANCE
# =============================================

class RepairMaintenance(models.Model):
    STATUS_DRAFT     = 'DRAFT'
    STATUS_SUBMITTED = 'SUBMITTED'
    STATUS_APPROVED  = 'APPROVED'
    STATUS_CHOICES   = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted to Bank'),
        ('APPROVED', 'Approved'),
    ]
    company                 = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='repairs')
    vehicle                 = models.ForeignKey('Vehicle', on_delete=models.SET_NULL, null=True, blank=True, related_name='repairs')
    repair_number           = models.CharField(max_length=20, blank=True)
    status                  = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    total_amount            = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes                   = models.TextField(blank=True)
    starting_km             = models.PositiveIntegerField(null=True, blank=True)
    starting_km_attachment  = models.FileField(upload_to='repair/km_attachments/', null=True, blank=True)
    ending_km               = models.PositiveIntegerField(null=True, blank=True)
    ending_km_attachment    = models.FileField(upload_to='repair/km_attachments/', null=True, blank=True)
    created_by              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='repairs_created')
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.repair_number:
            last = RepairMaintenance.objects.filter(company=self.company).order_by('-id').first()
            if last and last.repair_number.startswith('RM-'):
                self.repair_number = f'RM-{int(last.repair_number[3:]) + 1}'
            else:
                self.repair_number = 'RM-1'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.repair_number}"


class RepairItem(models.Model):
    repair      = models.ForeignKey(RepairMaintenance, on_delete=models.CASCADE, related_name='items')
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount      = models.DecimalField(max_digits=10, decimal_places=2)
    attachment  = models.FileField(upload_to='repair/attachments/', null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}: {self.amount}"


class RepairBankSettlement(models.Model):
    STATUS_PENDING  = 'PENDING_APPROVAL'
    STATUS_APPROVED = 'APPROVED'
    STATUS_CHOICES  = [
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
    ]
    repair        = models.OneToOneField(RepairMaintenance, on_delete=models.CASCADE, related_name='bank')
    bank_document = models.FileField(upload_to='repair/bank/', null=True, blank=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_APPROVAL')
    approved_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='repair_bank_approvals')
    approved_at   = models.DateTimeField(null=True, blank=True)
    submitted_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='repair_bank_submissions')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bank – {self.repair.repair_number}"


# =============================================
# HOLIDAY BANK APPROVAL MASTER
# =============================================

class HolidayBankApprover(models.Model):
    company    = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bank_approvers')
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='holiday_bank_approvals')
    is_active  = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bank_approvers_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'user')
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.username} – {self.company.name}"


class HolidayManager(models.Model):
    company    = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='holiday_managers')
    name       = models.CharField(max_length=200)
    mobile     = models.CharField(max_length=10)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='holiday_managers_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'mobile')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} – {self.mobile}"


class WhatsAppConfig(models.Model):
    """Singleton model — always use pk=1 via get_config()."""
    voucher_enabled  = models.BooleanField(default=True)
    function_enabled = models.BooleanField(default=True)
    holiday_enabled  = models.BooleanField(default=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "WhatsApp Configuration"

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "WhatsApp Configuration"