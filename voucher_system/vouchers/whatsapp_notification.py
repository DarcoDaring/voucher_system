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
import requests
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
        return _log_test_message(phone_number, message)

    phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
    access_token    = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')

    if not phone_number_id or not access_token:
        logger.error("WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN not set in settings.")
        return {"success": False, "error": "API credentials not configured"}

    try:
        resp = requests.post(
            f"https://graph.facebook.com/v18.0/{phone_number_id}/messages",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {"body": message},
            },
            timeout=15,
        )
        data = resp.json()
        if resp.ok:
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return {"success": True, "message_id": msg_id}
        logger.error(f"WhatsApp text send failed: {data}")
        return {"success": False, "error": str(data)}
    except Exception as e:
        logger.error(f"WhatsApp text send exception: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


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

def _notify_level_users(voucher, level, voucher_url, formatted_amount):
    """Send WhatsApp to all users at a specific approval level. Returns list of results."""
    from .models import CompanyMembership
    results = []
    memberships = CompanyMembership.objects.filter(
        company=voucher.company,
        designation=level.designation,
        group='Admin Staff',
        is_active=True,
        user__is_active=True
    ).select_related('user')

    if not memberships.exists():
        logger.warning(f"[WhatsApp] Level {level.order} ({level.designation.name}): no Admin Staff found")
        return results

    for membership in memberships:
        user = membership.user
        mobile = membership.mobile
        if not mobile:
            logger.warning(f"[WhatsApp] {user.username}: no mobile, skipping")
            continue
        clean_mobile = _clean_phone_number(mobile)
        if not clean_mobile:
            logger.warning(f"[WhatsApp] {user.username}: invalid mobile '{mobile}', skipping")
            continue

        message = _build_approval_message(
            voucher=voucher,
            total_amount=formatted_amount,
            approver_name=user.username,
            voucher_url=voucher_url,
            level_order=level.order,
            designation_name=level.designation.name,
        )
        result = send_whatsapp_message(clean_mobile, message)
        result['user'] = user.username
        result['mobile'] = clean_mobile
        results.append(result)
        if result.get('success'):
            logger.info(f"[WhatsApp] Notified {user.username} (+{clean_mobile}) — Level {level.order}")
        else:
            logger.error(f"[WhatsApp] Failed to notify {user.username}: {result.get('error')}")

    return results


def notify_approvers_new_voucher(voucher):
    """Called when a voucher is created — notifies Level 1 approvers only."""
    from .models import ApprovalLevel, WhatsAppConfig
    if not WhatsAppConfig.get_config().voucher_enabled:
        logger.info("[WhatsApp] Voucher notifications are disabled — skipping.")
        return []
    try:
        first_level = ApprovalLevel.objects.filter(
            company=voucher.company, is_active=True
        ).select_related('designation').order_by('order').first()

        if not first_level:
            logger.warning(f"[WhatsApp] No approval levels for {voucher.company.name}")
            return []

        voucher_url = _build_voucher_url(voucher)
        total_amount = sum(p.amount for p in voucher.particulars.all())
        formatted_amount = f"₹{total_amount:,.2f}"

        logger.info(f"[WhatsApp] Voucher {voucher.voucher_number} created — notifying Level {first_level.order} ({first_level.designation.name})")
        return _notify_level_users(voucher, first_level, voucher_url, formatted_amount)

    except Exception as e:
        logger.error(f"notify_approvers_new_voucher error: {e}", exc_info=True)
        return []


def notify_next_level_approvers(voucher, approved_level_order):
    """Called after an approval — notifies the next level in the chain."""
    from .models import ApprovalLevel, WhatsAppConfig
    if not WhatsAppConfig.get_config().voucher_enabled:
        return []
    try:
        next_level = ApprovalLevel.objects.filter(
            company=voucher.company,
            is_active=True,
            order__gt=approved_level_order
        ).select_related('designation').order_by('order').first()

        if not next_level:
            logger.info(f"[WhatsApp] Voucher {voucher.voucher_number}: Level {approved_level_order} was the last — no further notifications.")
            return []

        voucher_url = _build_voucher_url(voucher)
        total_amount = sum(p.amount for p in voucher.particulars.all())
        formatted_amount = f"₹{total_amount:,.2f}"

        logger.info(f"[WhatsApp] Voucher {voucher.voucher_number} — Level {approved_level_order} approved, notifying Level {next_level.order} ({next_level.designation.name})")
        return _notify_level_users(voucher, next_level, voucher_url, formatted_amount)

    except Exception as e:
        logger.error(f"notify_next_level_approvers error: {e}", exc_info=True)
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

def _build_voucher_url(voucher):
    """
    Return a clickable HTTP URL that WhatsApp will hyperlink.
    The Django view at /open-voucher/<pk>/ redirects to voucher://detail/<pk>,
    which Android intercepts to open the Flutter app.
    """
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
    return f"{site_url}/open-voucher/{voucher.id}/"


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
# PDF GENERATION (Playwright – exact browser print output)
# =============================================

def _logo_as_base64(company) -> str:
    """Return a base64 data URI for the company logo, or empty string."""
    import os, base64
    from django.conf import settings as s

    if not company or not company.logo:
        return ''
    try:
        path = os.path.join(str(s.MEDIA_ROOT), str(company.logo))
        if not os.path.exists(path):
            return ''
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        ext  = os.path.splitext(path)[1].lower().lstrip('.')
        mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'png': 'image/png',  'gif': 'image/gif'}.get(ext, 'image/png')
        return f"data:{mime};base64,{data}"
    except Exception:
        return ''


def _generate_pdf(template_name: str, context: dict, company=None) -> bytes:
    """
    Render a Django template to PDF bytes using Playwright (headless Chromium).
    Produces the exact same output as clicking Print in the browser.
    """
    import re
    from django.template.loader import render_to_string
    from playwright.sync_api import sync_playwright

    html = render_to_string(template_name, context)

    # Embed company logo as base64 so Playwright can render it
    # (covers both relative /media/... URLs and broken ://host/media/... patterns)
    if company and company.logo:
        logo_b64 = _logo_as_base64(company)
        if logo_b64:
            logo_url = company.logo.url          # e.g. /media/logos/logo.png
            logo_name = logo_url.split('/')[-1]  # e.g. logo.png
            # replace any src attribute that references this logo
            html = re.sub(
                r'src="[^"]*' + re.escape(logo_name) + r'"',
                f'src="{logo_b64}"',
                html,
            )

    # Remove window.print() so Chromium doesn't open a print dialog
    html = re.sub(r'window\s*\.\s*print\s*\(\s*\)', '', html)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        # wait_until='networkidle' lets Bootstrap CDN finish loading
        page.set_content(html, wait_until='networkidle')
        pdf_bytes = page.pdf(format='A4', print_background=True)
        browser.close()

    return pdf_bytes


# =============================================
# META CLOUD API – MEDIA UPLOAD + DOCUMENT SEND
# =============================================

def _upload_whatsapp_media(pdf_bytes: bytes, filename: str) -> str:
    """
    Upload a PDF to WhatsApp Media API.
    Returns the media_id string, or '' on failure.
    """
    phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
    access_token    = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')

    if not phone_number_id or not access_token:
        logger.error("WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN not set in settings.")
        return ''

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/media"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            data={"messaging_product": "whatsapp", "type": "application/pdf"},
            files={"file": (filename, pdf_bytes, "application/pdf")},
            timeout=30,
        )
        data = resp.json()
        if not resp.ok or 'id' not in data:
            logger.error(f"WhatsApp media upload failed: {data}")
            return ''
        return data['id']
    except Exception as e:
        logger.error(f"WhatsApp media upload exception: {e}", exc_info=True)
        return ''


def _send_whatsapp_document(phone_number: str, media_id: str, filename: str, caption: str = '') -> dict:
    """
    Send a document message via Meta Cloud API using an uploaded media_id.
    Returns {"success": True/False, ...}.
    """
    phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
    access_token    = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename,
            "caption": caption,
        },
    }
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        data = resp.json()
        if resp.ok:
            msg_id = data.get('messages', [{}])[0].get('id', '')
            return {"success": True, "message_id": msg_id}
        logger.error(f"WhatsApp document send failed: {data}")
        return {"success": False, "error": str(data)}
    except Exception as e:
        logger.error(f"WhatsApp document send exception: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# =============================================
# FUNCTION PROSPECT – WHATSAPP PDF SEND
# =============================================

def send_function_prospect_whatsapp(function) -> dict:
    """
    Generate the function prospectus PDF and send it via WhatsApp
    to the first contact number on the booking.
    Called after FunctionConfirmAPI saves the booking.
    """
    from .models import WhatsAppConfig
    if not WhatsAppConfig.get_config().function_enabled:
        logger.info("[WhatsApp] Function notifications are disabled — skipping.")
        return {"success": False, "error": "Function WhatsApp notifications are disabled"}
    try:
        contact_numbers = function.contact_numbers or []
        if not contact_numbers:
            logger.warning(f"[WhatsApp] Function {function.function_number}: no contact numbers, skipping.")
            return {"success": False, "error": "No contact number"}

        raw_number = contact_numbers[0]
        phone = _clean_phone_number(str(raw_number))
        if not phone:
            logger.warning(f"[WhatsApp] Function {function.function_number}: invalid number '{raw_number}', skipping.")
            return {"success": False, "error": "Invalid phone number"}

        company = function.company
        context = {
            "function": function,
            "company": company,
        }

        pdf_bytes = _generate_pdf("vouchers/function_print.html", context, company=company)
        filename  = f"Function_Prospectus_{function.function_number}.pdf"

        if not WHATSAPP_LIVE_MODE:
            print(f"\n{'='*60}")
            print(f"[WhatsApp PDF TEST] Function Prospectus")
            print(f"  To      : +{phone}")
            print(f"  File    : {filename}")
            print(f"  PDF size: {len(pdf_bytes)} bytes")
            print(f"{'='*60}\n")
            return {"success": True, "mode": "TEST", "phone": phone, "filename": filename}

        media_id = _upload_whatsapp_media(pdf_bytes, filename)
        if not media_id:
            return {"success": False, "error": "Media upload failed"}

        contact_parts = []
        if company.phone: contact_parts.append(company.phone)
        if company.email: contact_parts.append(company.email)
        contact_line = "\n\nFor booking related queries and enquiries contact: " + " | ".join(contact_parts) if contact_parts else ""

        caption = (
            f"*{function.function_name}*\n"
            f"ID: {function.function_number}\n"
            f"Date: {function.function_date.strftime('%d %b %Y')}\n"
            f"Time: {function.time_from.strftime('%I:%M %p')} – {function.time_to.strftime('%I:%M %p')}\n"
            f"Venue: {function.location}\n"
            f"Booked By: {function.booked_by}"
            f"{contact_line}"
        )
        return _send_whatsapp_document(phone, media_id, filename, caption)

    except Exception as e:
        logger.error(f"send_function_prospect_whatsapp error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# =============================================
# HOLIDAY ORDER FORM – WHATSAPP PDF SEND
# =============================================

def send_holiday_orderform_whatsapp(booking) -> dict:
    """
    Generate the holiday order form PDF and send it via WhatsApp
    to the primary contact number on the booking.
    Called after HolidayConfirmAPI saves the booking.
    """
    from .models import WhatsAppConfig
    if not WhatsAppConfig.get_config().holiday_enabled:
        logger.info("[WhatsApp] Holiday notifications are disabled — skipping.")
        return {"success": False, "error": "Holiday WhatsApp notifications are disabled"}
    try:
        raw_number = booking.contact_number or ''
        phone = _clean_phone_number(str(raw_number))
        if not phone:
            logger.warning(f"[WhatsApp] Booking {booking.booking_number}: invalid number '{raw_number}', skipping.")
            return {"success": False, "error": "Invalid phone number"}

        from .holiday_views import number_to_words
        company = booking.company
        context = {
            "booking": booking,
            "company": company,
            "balance_in_words": number_to_words(booking.balance_amount or 0),
        }

        pdf_bytes = _generate_pdf("vouchers/holiday_print.html", context, company=company)
        filename  = f"Order_Form_{booking.booking_number}.pdf"

        if not WHATSAPP_LIVE_MODE:
            print(f"\n{'='*60}")
            print(f"[WhatsApp PDF TEST] Holiday Order Form")
            print(f"  To      : +{phone}")
            print(f"  File    : {filename}")
            print(f"  PDF size: {len(pdf_bytes)} bytes")
            print(f"{'='*60}\n")
            return {"success": True, "mode": "TEST", "phone": phone, "filename": filename}

        media_id = _upload_whatsapp_media(pdf_bytes, filename)
        if not media_id:
            return {"success": False, "error": "Media upload failed"}

        contact_parts = []
        if company.phone: contact_parts.append(company.phone)
        if company.email: contact_parts.append(company.email)
        contact_line = "\n\nFor booking related queries and enquiries contact: " + " | ".join(contact_parts) if contact_parts else ""

        caption = (
            f"*{booking.purpose_of_booking}*\n"
            f"ID: {booking.booking_number}\n"
            f"Date: {booking.trip_date.strftime('%d %b %Y')}\n"
            f"Time: {booking.departure_time.strftime('%I:%M %p')}\n"
            f"From: {booking.departure_location}\n"
            f"Destination: {booking.destination}\n"
            f"Booked By: {booking.booked_by}"
            f"{contact_line}"
        )
        return _send_whatsapp_document(phone, media_id, filename, caption)

    except Exception as e:
        logger.error(f"send_holiday_orderform_whatsapp error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


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
