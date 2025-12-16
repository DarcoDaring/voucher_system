from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os
from decimal import Decimal, InvalidOperation

class Designation(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='designations')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=True)
    
    # NEW: Mobile Number
    mobile = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Mobile number (e.g., +91 9876543210 or 9876543210)"
    )
    # NEW: User signature
    signature = models.ImageField(
        upload_to='signatures/',
        null=True,
        blank=True,
        help_text="Upload your digital signature (PNG/JPG, transparent background recommended)"
    )

    def __str__(self):
        return f"{self.user.username} - {self.designation}"


class Voucher(models.Model):
    PAYMENT_TYPES = (
        ('CASH', 'Cash'),
        ('CHEQUE', 'Cheque'),
        ('PETTY_CASH', 'Petty Cash'),
    )

    voucher_number = models.CharField(max_length=20, unique=True, blank=True)
    voucher_date = models.DateField()
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    name_title = models.CharField(max_length=5, choices=[('MR', 'Mr.'), ('MRS', 'Mrs.'), ('MS', 'Ms.')])
    pay_to = models.CharField(max_length=200)
    
    # REMOVED: Old single main attachment (now using MainAttachment model below)
    # attachment = models.FileField(upload_to='vouchers/attachments/', null=True, blank=True)

    # CHEQUE FIELDS
    cheque_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Required only for Cheque payments"
    )

    # REMOVED: Old single cheque attachment (now using ChequeAttachment model below)
    # cheque_attachment = models.FileField(upload_to='vouchers/cheques/', null=True, blank=True)

    cheque_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date on the cheque - required for Cheque payments"
    )

    # ACCOUNT DETAILS → REQUIRED FOR CHEQUE
    account_details = models.ForeignKey(
        'AccountDetail',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Bank account for Cheque payments"
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
            last_voucher = Voucher.objects.order_by('-id').first()
            if last_voucher and last_voucher.voucher_number.startswith('VCH'):
                num = int(last_voucher.voucher_number[3:]) + 1
                self.voucher_number = f'VCH{num:04d}'
            else:
                self.voucher_number = 'VCH0001'

        # Save snapshot on first save (creation)
        if not self.pk:
            super().save(*args, **kwargs)  # Save first to get PK
            self.required_approvers_snapshot = self._get_current_required_approvers()
            self.save(update_fields=['required_approvers_snapshot'])
        else:
            super().save(*args, **kwargs)

    def _get_current_required_approvers(self):
        """Helper: Get current required approvers from active levels."""
        levels = ApprovalLevel.objects.filter(is_active=True).select_related('designation').order_by('order')
        usernames = []
        for level in levels:
            users = UserProfile.objects.filter(
                designation=level.designation,
                user__groups__name='Admin Staff'
            ).values_list('user__username', flat=True).distinct()
            usernames.extend(users)
        return usernames

    def __str__(self):
        return self.voucher_number

    @property
    def required_approvers(self):
        if self.status in ['APPROVED', 'REJECTED']:
            return self.required_approvers_snapshot or []
        else:
            return self._get_current_required_approvers()

    def _update_status_if_all_approved(self):
        # If any rejection → REJECTED
        if self.approvals.filter(status='REJECTED').exists():
            self.status = 'REJECTED'
            self.save(update_fields=['status'])
            return

        # Get active approval levels
        levels = ApprovalLevel.objects.filter(is_active=True).order_by('order')
        if not levels.exists():
            self.status = 'APPROVED'
            self.save(update_fields=['status'])
            return

        approved_usernames = set(
            self.approvals.filter(status='APPROVED')
                .values_list('approver__username', flat=True)
        )

        # Check: for each active level, is AT LEAST ONE user from that designation approved?
        for level in levels:
            level_users = UserProfile.objects.filter(
                designation=level.designation,
                user__groups__name='Admin Staff',
                user__is_active=True
            ).values_list('user__username', flat=True)

            # If no users in this designation → skip (shouldn't happen)
            if not level_users:
                continue

            # If NONE of the users in this level have approved → not done yet
            if not any(username in approved_usernames for username in level_users):
                self.status = 'PENDING'
                self.save(update_fields=['status'])
                return

        # All levels have at least one approval → APPROVED
        self.status = 'APPROVED'
        self.save(update_fields=['status'])

    def clean(self):
        from django.core.exceptions import ValidationError

        # CHEQUE VALIDATION
        if self.payment_type == 'CHEQUE':
            if not self.cheque_number:
                raise ValidationError("Cheque number is required for Cheque payments.")
            if not self.cheque_attachments.exists():  # Now checks related objects
                raise ValidationError("At least one cheque attachment is required for Cheque payments.")
            if not self.cheque_date:
                raise ValidationError("Cheque date is required for Cheque payments.")
            if not self.account_details:
                raise ValidationError("Account Details is required for Cheque payments.")
        else:
            # Clear cheque fields if not CHEQUE
            self.cheque_number = None
            self.cheque_date = None
            self.account_details = None


class Particular(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='particulars')
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # REMOVED: Old single attachment (now using ParticularAttachment model below)
    # attachment = models.FileField(upload_to='vouchers/particulars/', help_text="...")

    def __str__(self):
        return f"{self.description} - {self.amount}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.attachments.exists():  # Now checks multiple attachments
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
    designation = models.OneToOneField(Designation, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(unique=True, help_text="Lower number = earlier in approval chain")
    is_active = models.BooleanField(default=True, help_text="Only active levels require approval")
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        verbose_name = "Approval Level"
        verbose_name_plural = "Approval Levels"

    def __str__(self):
        return f"{self.order}. {self.designation.name} ({'Active' if self.is_active else 'Inactive'})"


class AccountDetail(models.Model):
    bank_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='account_details')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('bank_name', 'account_number')
        ordering = ['bank_name']

    def __str__(self):
        return f"{self.bank_name} / {self.account_number}"


# === NEW: COMPANY DETAIL (SINGLETON - ONLY ONE RECORD) ===
class CompanyDetail(models.Model):
    """
    matedocstring
    Singleton model: Only ONE company detail exists at a time.
    Used for: Company Name, GST, PAN, Address, Logo, Email, Phone.
    """
    name = models.CharField(max_length=200, help_text="Company Name")
    gst_no = models.CharField(max_length=20, blank=True, null=True, help_text="GST Number (e.g., 22AAAAA0000A1Z5)")
    pan_no = models.CharField(max_length=15, blank=True, null=True, help_text="PAN Number (e.g., AAAAA0000A)")
    address = models.TextField(blank=True, null=True, help_text="Full company address")
    email = models.EmailField(blank=True, null=True, help_text="Company email address")
    phone = models.CharField(max_length=20, blank=True, null=True, help_text="Company phone number")
    logo = models.ImageField(
        upload_to='company/logo/',
        null=True,
        blank=True,
        help_text="Company logo (PNG/JPG, max 2MB)"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='company_details_updated'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Detail"
        verbose_name_plural = "Company Details"

    def __str__(self):
        return self.name or "Company"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        CompanyDetail.objects.exclude(pk=1).delete()

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


# =============================================
# NEW MODELS FOR MULTIPLE FILE UPLOADS
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
    
#Create FunctionBooking 

class FunctionBooking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Confirmation'),
        ('CONFIRMED', 'Function Confirmed'),
        ('CANCELLED', 'Cancelled'),
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
    
    function_number = models.CharField(max_length=20, unique=True, blank=True)
    function_date = models.DateField()
    time_from = models.TimeField()
    time_to = models.TimeField()
    function_name = models.CharField(max_length=200)
    booked_by = models.CharField(max_length=200, help_text="Name of person/company who booked")
    
    # Multiple contact numbers (stored as JSON array)
    contact_numbers = models.JSONField(default=list, help_text="List of contact numbers")
    
    address = models.TextField(max_length=500)
    
    # UPDATED: Menu items stored as JSON object with categories
    menu_items = models.JSONField(
        default=dict, 
        help_text="Menu items categorized: {welcome_drink, starters, main_course, desserts}"
    )
    
    no_of_pax = models.IntegerField()
    rate_per_pax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # GST option
    gst_option = models.CharField(max_length=20, choices=GST_CHOICES, default='INCLUDING')
    
    # Hall rent (optional)
    hall_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    
    # UPDATED: Location moved to creation time (not confirmation)
    location = models.CharField(
        max_length=50, 
        choices=LOCATION_CHOICES, 
        help_text="Location where the function will be held"
    )
    
    # Extra charges (stored as JSON array of {description, rate})
    extra_charges = models.JSONField(default=list, help_text="List of extra charges with description and rate")
    
    # Calculated total amount
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Confirmation fields
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
    # NEW: Special instructions for confirmed functions
    special_instructions = models.TextField(
        blank=True,
        null=True,
        help_text="Special instructions or notes for the function"
    )
    is_completed = models.BooleanField(default=False, verbose_name="Marked as Completed")
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
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.function_number} - {self.function_name}"
    
    def save(self, *args, **kwargs):
        if not self.function_number:
            last_function = FunctionBooking.objects.order_by('-id').first()
            if last_function and last_function.function_number.startswith('FN'):
                num = int(last_function.function_number[2:]) + 1
                self.function_number = f'FN{num:04d}'
            else:
                self.function_number = 'FN0001'

        # Always recalculate total
        self.calculate_total_amount()

        # ✅ ALWAYS recalculate due amount
        total = Decimal(self.total_amount or 0)
        advance = Decimal(self.advance_amount or 0)
        self.due_amount = total - advance

        # Prevent negative due
        if self.due_amount < 0:
            self.due_amount = Decimal('0.00')

        super().save(*args, **kwargs)

    
    def calculate_total_amount(self):
        """Calculate total amount based on pax, rate, GST, hall rent and extra charges"""
        base_amount = Decimal(self.no_of_pax) * Decimal(self.rate_per_pax)
        
        # Apply GST
        if self.gst_option == 'INCLUDING':
            amount_with_gst = base_amount * Decimal('1.05')  # Add 5% GST
        else:
            amount_with_gst = (base_amount*100)/105
        
        # Add hall rent
        hall_rent = Decimal(self.hall_rent or 0)
        
        # Add extra charges
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
    
    # Get current time in configured timezone (Asia/Kolkata)
    now = timezone.localtime(timezone.now())
    
    # Create timezone-aware datetime for function end time
    function_end_datetime = timezone.make_aware(
        datetime.datetime.combine(self.function_date, self.time_to)
    )
    
    # Function is completed if current time >= function end time
    return now >= function_end_datetime


class UserPermission(models.Model):
    """
    Granular permissions for each user.
    Allows superusers to control what each user can do.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='permissions')
    
    # Voucher Permissions
    can_create_voucher = models.BooleanField(
        default=True,
        help_text="User can create new vouchers"
    )
    can_edit_voucher = models.BooleanField(
        default=False,
        help_text="User can edit existing vouchers (only accountants, only pending, only if no approvals yet)"
    )
    can_view_voucher_list = models.BooleanField(
        default=True,
        help_text="User can view voucher list page"
    )
    can_view_voucher_detail = models.BooleanField(
        default=True,
        help_text="User can view individual voucher details"
    )
    can_print_voucher = models.BooleanField(
        default=True,
        help_text="User can print vouchers"
    )
    # Function Permissions
    can_create_function = models.BooleanField(
        default=True,
        help_text="User can create new function bookings"
    )
    can_edit_function = models.BooleanField(
        default=False,
        help_text="User can edit existing function bookings"
    )
    can_delete_function = models.BooleanField(
        default=False,
        help_text="User can delete function bookings"
    )
    can_view_function_list = models.BooleanField(
        default=True,
        help_text="User can view function calendar/list page"
    )
    can_view_function_detail = models.BooleanField(
        default=True,
        help_text="User can view individual function details"
    )
    can_print_function = models.BooleanField(
        default=True,
        help_text="User can print function prospectus"
    )
    
    # Metadata
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permission_updates'
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"
    
    def __str__(self):
        return f"Permissions for {self.user.username}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """
        Get or create permissions for a user with default values.
        """
        obj, created = cls.objects.get_or_create(
            user=user,
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
        return obj