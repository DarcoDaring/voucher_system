# vouchers/whatsapp_notification.py
"""
WhatsApp Notification Service for Voucher Approvals
=====================================================
This module handles sending WhatsApp messages to admin staff
when a new voucher is created and requires their approval.

TESTING MODE: Messages are logged to a file instead of being sent.
To go live, replace `send_whatsapp_message()` with your actual API call.
"""

import logging
import json
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

# =============================================
# CONFIGURATION
# =============================================

# Set to True to actually send messages via API
# Set to False to only log messages (for testing)
WHATSAPP_LIVE_MODE = getattr(settings, 'WHATSAPP_LIVE_MODE', False)

# Your WhatsApp API credentials (set these in Django settings.py)
# WHATSAPP_API_URL = "https://api.whatsapp.com/..."  # e.g. Twilio, Meta, Gupshup
# WHATSAPP_API_KEY = "your_api_key_here"
# WHATSAPP_FROM_NUMBER = "+91XXXXXXXXXX"


# =============================================
# CORE SEND FUNCTION (SWAP THIS FOR REAL API)
# =============================================

def send_whatsapp_message(phone_number: str, message: str) -> dict:
    """
    Send a WhatsApp message to a phone number.
    
    In TEST MODE: Logs the message to file and console.
    In LIVE MODE: Replace the body of this function with your API call.
    
    Args:
        phone_number: Recipient's phone number (e.g. "919876543210")
        message: The text message to send
    
    Returns:
        dict: {"success": True/False, "message_id": "...", "error": "..."}
    """
    
    if not WHATSAPP_LIVE_MODE:
        # ===== TEST MODE: Log to file =====
        return _log_test_message(phone_number, message)
    
    else:
        # ===== LIVE MODE: Replace with your actual API =====
        # Example using Twilio:
        # from twilio.rest import Client
        # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # message = client.messages.create(
        #     from_=f"whatsapp:{settings.WHATSAPP_FROM_NUMBER}",
        #     body=message,
        #     to=f"whatsapp:+{phone_number}"
        # )
        # return {"success": True, "message_id": message.sid}
        
        # Example using Meta Cloud API:
        # import requests
        # response = requests.post(
        #     f"https://graph.facebook.com/v17.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
        #     headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
        #     json={
        #         "messaging_product": "whatsapp",
        #         "to": phone_number,
        #         "type": "text",
        #         "text": {"body": message}
        #     }
        # )
        # data = response.json()
        # return {"success": response.ok, "message_id": data.get("messages", [{}])[0].get("id")}
        
        logger.warning("WHATSAPP_LIVE_MODE=True but no API implementation found!")
        return {"success": False, "error": "No API implementation configured"}


def _log_test_message(phone_number: str, message: str) -> dict:
    """Log message to console and file for testing."""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = {
        "timestamp": timestamp,
        "to": phone_number,
        "message": message,
        "status": "TEST_MODE"
    }
    
    # Print to Django console (visible in runserver output)
    print("\n" + "="*60)
    print("📱 WHATSAPP NOTIFICATION (TEST MODE)")
    print("="*60)
    print(f"  To     : +{phone_number}")
    print(f"  Time   : {timestamp}")
    print(f"  Message:")
    print(f"  {message}")
    print("="*60 + "\n")
    
    # Also log to Django logger
    safe_msg = message[:100].encode('ascii', errors='replace').decode('ascii')
    logger.info(f"[WhatsApp TEST] To: +{phone_number} | Message: {safe_msg}...")
        
    # Write to a log file for easy inspection
    try:
        import os
        log_dir = getattr(settings, 'BASE_DIR', '.')
        log_path = os.path.join(str(log_dir), 'whatsapp_test_log.json')
        
        # Read existing logs
        logs = []
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        
        logs.append(log_entry)
        
        # Keep last 100 entries
        logs = logs[-100:]
        
        with open(log_path, 'w') as f:
            json.dump(logs, f, indent=2)
            
    except Exception as e:
        logger.warning(f"Could not write WhatsApp test log: {e}")
    
    return {
        "success": True,
        "message_id": f"test_{datetime.now().timestamp()}",
        "mode": "TEST"
    }


# =============================================
# VOUCHER NOTIFICATION FUNCTION
# =============================================

def notify_approvers_new_voucher(voucher, request=None):
    from .models import ApprovalLevel, CompanyMembership
    try:
        voucher_url = _build_voucher_url(voucher, request)
        total_amount = sum(p.amount for p in voucher.particulars.all())
        formatted_amount = f"₹{total_amount:,.2f}"

        levels = ApprovalLevel.objects.filter(
            company=voucher.company, is_active=True
        ).select_related('designation').order_by('order')

        if not levels.exists():
            print(f"⚠️  No approval levels configured for {voucher.company.name}")
            return

        print(f"\n🔍 APPROVAL NOTIFICATION DEBUG — Voucher: {voucher.voucher_number}")
        print(f"   Company : {voucher.company.name}")
        print(f"   Levels  : {levels.count()} active level(s)")

        notified_users = set()
        results = []

        for level in levels:
            print(f"\n   📌 Level {level.order} — Designation: {level.designation.name}")

            memberships = CompanyMembership.objects.filter(
                company=voucher.company,
                designation=level.designation,
                group='Admin Staff',
                is_active=True,
                user__is_active=True
            ).select_related('user')

            if not memberships.exists():
                print(f"      ❌ No active Admin Staff found with designation '{level.designation.name}'")
                continue

            for membership in memberships:
                user = membership.user
                print(f"      👤 User: {user.username} | Mobile: '{membership.mobile or 'NOT SET'}'")

                if user.id in notified_users:
                    print(f"         ⏭️  Already notified — skipping")
                    continue

                mobile = membership.mobile
                if not mobile:
                    print(f"         ❌ No mobile number — skipping")
                    continue

                clean_mobile = _clean_phone_number(mobile)
                if not clean_mobile:
                    print(f"         ❌ Invalid mobile '{mobile}' — skipping")
                    continue

                message = _build_approval_message(
                    voucher=voucher,
                    total_amount=formatted_amount,
                    approver_name=user.username,
                    voucher_url=voucher_url,
                    level_order=level.order,
                    designation_name=level.designation.name
                )

                result = send_whatsapp_message(clean_mobile, message)
                result['user'] = user.username
                result['mobile'] = clean_mobile
                results.append(result)
                notified_users.add(user.id)

                if result.get('success'):
                    print(f"         ✅ Notified successfully")
                else:
                    print(f"         ❌ Send failed: {result.get('error')}")

        print(f"\n   ✅ Total notified: {len(notified_users)} user(s)\n")
        return results

    except Exception as e:
        logger.error(f"Error sending voucher notifications: {e}", exc_info=True)
        return []

# =============================================
# MESSAGE BUILDER
# =============================================

def _build_approval_message(voucher, total_amount, approver_name, voucher_url, level_order, designation_name):
    """
    Build the WhatsApp message text.
    Customize this as needed.
    """
    
    created_by = voucher.created_by.username
    company_name = voucher.company.name
    pay_to = f"{voucher.get_name_title_display()} {voucher.pay_to}"
    payment_type = voucher.get_payment_type_display()
    from datetime import date
    if isinstance(voucher.voucher_date, str):
        from datetime import datetime
        voucher_date = datetime.strptime(voucher.voucher_date, "%Y-%m-%d").strftime("%d %b %Y")
    else:
        voucher_date = voucher.voucher_date.strftime("%d %b %Y")
    
    message = (
        f"🔔 *Voucher Approval Required*\n\n"
        f"Hello {approver_name},\n\n"
        f"A new voucher has been created and requires your approval.\n\n"
        f"📋 *Details:*\n"
        f"• Voucher No : *{voucher.voucher_number}*\n"
        f"• Date       : {voucher_date}\n"
        f"• Pay To     : {pay_to}\n"
        f"• Amount     : *{total_amount}*\n"
        f"• Payment    : {payment_type}\n"
        f"• Company    : {company_name}\n"
        f"• Created By : {created_by}\n\n"
        f"🔗 *View & Approve:*\n"
        f"{voucher_url}\n\n"
        f"_You are receiving this as {designation_name} (Level {level_order} approver)_"
    )
    
    return message


# =============================================
# HELPER FUNCTIONS
# =============================================

def _build_voucher_url(voucher, request=None):
    """Build the absolute URL for the voucher detail page."""
    
    relative_url = f"/vouchers/{voucher.id}/"
    
    if request:
        try:
            return request.build_absolute_uri(relative_url)
        except Exception:
            pass
    
    # Fallback: use SITE_URL from settings if available
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site_url:
        return f"{site_url}{relative_url}"
    
    # Last fallback: just return relative URL
    return relative_url


def _clean_phone_number(phone: str) -> str:
    """
    Clean and normalize a phone number.
    Returns a string like "919876543210" (country code + number, no +)
    Returns empty string if invalid.
    """
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = ''.join(c for c in str(phone) if c.isdigit())
    
    if not digits:
        return ""
    
    # If it's a 10-digit Indian number, add country code
    if len(digits) == 10:
        return f"91{digits}"
    
    # If it already has country code (12 digits for India)
    if len(digits) >= 11:
        return digits
    
    return digits if len(digits) >= 10 else ""


# =============================================
# API: VIEW NOTIFICATION LOGS (For Testing)
# =============================================

def get_test_logs(limit=20):
    """Read the test log file and return recent notifications."""
    import os
    
    try:
        log_dir = getattr(settings, 'BASE_DIR', '.')
        log_path = os.path.join(str(log_dir), 'whatsapp_test_log.json')
        
        if not os.path.exists(log_path):
            return []
        
        with open(log_path, 'r') as f:
            logs = json.load(f)
        
        return list(reversed(logs))[:limit]
        
    except Exception as e:
        logger.error(f"Could not read WhatsApp test log: {e}")
        return []
