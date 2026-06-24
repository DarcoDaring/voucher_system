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

        if not WHATSAPP_LIVE_MODE:
            message = _build_approval_message(
                voucher=voucher,
                total_amount=formatted_amount,
                approver_name=user.username,
                voucher_url=voucher_url,
                level_order=level.order,
                designation_name=level.designation.name,
            )
            result = _log_test_message(clean_mobile, message)
        else:
            from datetime import datetime as _dt
            vdate = voucher.voucher_date
            voucher_date_str = vdate.strftime('%d %b %Y') if hasattr(vdate, 'strftime') else _dt.strptime(vdate, "%Y-%m-%d").strftime('%d %b %Y')
            result = _send_whatsapp_template(clean_mobile, "voucher_approval_request", {
                "approver_name": user.username,
                "voucher_number": voucher.voucher_number,
                "voucher_date": voucher_date_str,
                "pay_to": f"{voucher.get_name_title_display()} {voucher.pay_to}",
                "amount": formatted_amount,
                "payment_type": voucher.get_payment_type_display(),
                "company_name": voucher.company.name,
                "created_by": voucher.created_by.username,
                "approval_link": voucher_url,
                "designation": level.designation.name,
                "level_order": str(level.order),
            })
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
        f"_You are receiving this as {designation_name} (Level {level_order} approver)_\n\n"
        f"Thank you."
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


def _generate_pdf(template_name: str, context: dict, company=None, page_ranges: str = '') -> bytes:
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
        pdf_kwargs = {'format': 'A4', 'print_background': True}
        if page_ranges:
            pdf_kwargs['page_ranges'] = page_ranges
        pdf_bytes = page.pdf(**pdf_kwargs)
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


def _send_whatsapp_template(phone_number: str, template_name: str, body_params: dict) -> dict:
    """Send a text-only template message via Meta Cloud API."""
    phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
    access_token    = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "parameter_name": k, "text": str(v)}
                    for k, v in body_params.items()
                ]
            }]
        }
    }
    try:
        resp = requests.post(url, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}, json=payload, timeout=15)
        data = resp.json()
        if resp.ok:
            return {"success": True, "message_id": data.get("messages", [{}])[0].get("id", "")}
        logger.error(f"WhatsApp template send failed: {data}")
        return {"success": False, "error": str(data)}
    except Exception as e:
        logger.error(f"WhatsApp template send exception: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _send_whatsapp_template_with_document(phone_number: str, template_name: str, media_id: str, filename: str, body_params: dict) -> dict:
    """Send a template message with document header via Meta Cloud API."""
    phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
    access_token    = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [
                {
                    "type": "header",
                    "parameters": [{"type": "document", "document": {"id": media_id, "filename": filename}}]
                },
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "parameter_name": k, "text": str(v)}
                        for k, v in body_params.items()
                    ]
                }
            ]
        }
    }
    try:
        resp = requests.post(url, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}, json=payload, timeout=15)
        data = resp.json()
        if resp.ok:
            return {"success": True, "message_id": data.get("messages", [{}])[0].get("id", "")}
        logger.error(f"WhatsApp template+document send failed: {data}")
        return {"success": False, "error": str(data)}
    except Exception as e:
        logger.error(f"WhatsApp template+document send exception: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


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
    to the first contact number on the booking, and to all managers.
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

        pdf_bytes = _generate_pdf("vouchers/function_print.html", context, company=company, page_ranges='1')
        filename  = f"Function_Prospectus_{function.function_number}.pdf"
        manager_phones = _get_manager_phones(company)

        contact_parts = []
        if company.phone: contact_parts.append(company.phone)
        if company.email: contact_parts.append(company.email)
        contact_info = " | ".join(contact_parts) if contact_parts else "N/A"

        template_params = {
            "function_name": function.function_name,
            "function_number": function.function_number,
            "function_date": function.function_date.strftime('%d %b %Y'),
            "time_from": function.time_from.strftime('%I:%M %p'),
            "time_to": function.time_to.strftime('%I:%M %p'),
            "location": function.location,
            "booked_by": function.booked_by,
            "contact_info": contact_info,
        }

        if not WHATSAPP_LIVE_MODE:
            customer_msg = (
                f"[Function Prospectus]\n"
                f"Function : {function.function_number}\n"
                f"Name     : {function.function_name}\n"
                f"Date     : {template_params['function_date']}\n"
                f"Location : {function.location}\n"
                f"File     : {filename} ({len(pdf_bytes)} bytes)"
            )
            _log_test_message(phone, customer_msg)
            for name, mp in manager_phones:
                _log_test_message(mp, f"[Manager Copy – {name}]\n{customer_msg}")
            return {"success": True, "mode": "TEST", "phone": phone, "filename": filename}

        media_id = _upload_whatsapp_media(pdf_bytes, filename)
        if not media_id:
            return {"success": False, "error": "Media upload failed"}

        # Send to customer
        result = _send_whatsapp_template_with_document(phone, "function_prospect_pdf", media_id, filename, template_params)

        # Send same template+PDF to every manager
        for name, mp in manager_phones:
            try:
                _send_whatsapp_template_with_document(mp, "function_prospect_pdf", media_id, filename, template_params)
                logger.info(f"[WhatsApp] Manager copy sent to {name} (+{mp})")
            except Exception as me:
                logger.error(f"[WhatsApp] Manager copy failed for {name} (+{mp}): {me}")

        return result

    except Exception as e:
        logger.error(f"send_function_prospect_whatsapp error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# =============================================
# HOLIDAY ORDER FORM – WHATSAPP PDF SEND
# =============================================

def _get_manager_phones(company) -> list:
    """Return a list of cleaned phone numbers for all HolidayManagers of the company."""
    from .models import HolidayManager
    phones = []
    for m in HolidayManager.objects.filter(company=company):
        p = _clean_phone_number(m.mobile)
        if p:
            phones.append((m.name, p))
    return phones


def send_holiday_orderform_whatsapp(booking) -> dict:
    """
    Generate the holiday order form PDF and send it via WhatsApp
    to the primary contact number on the booking, and to all managers.
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
        manager_phones = _get_manager_phones(company)

        contact_parts = []
        if company.phone: contact_parts.append(company.phone)
        if company.email: contact_parts.append(company.email)
        contact_info = " | ".join(contact_parts) if contact_parts else "N/A"

        template_params = {
            "purpose": booking.purpose_of_booking or "N/A",
            "booking_number": booking.booking_number or "N/A",
            "trip_date": booking.trip_date.strftime('%d %b %Y') if booking.trip_date else "N/A",
            "departure_time": booking.departure_time.strftime('%I:%M %p') if booking.departure_time else "N/A",
            "departure_location": booking.departure_location or "N/A",
            "destination": booking.destination or "N/A",
            "booked_by": booking.booked_by or "N/A",
            "contact_info": contact_info,
        }

        if not WHATSAPP_LIVE_MODE:
            customer_msg = (
                f"[Holiday Order Form]\n"
                f"Booking : {booking.booking_number}\n"
                f"Customer: {booking.booked_by}\n"
                f"Trip    : {template_params['trip_date']}\n"
                f"Places  : {booking.destination}\n"
                f"File    : {filename} ({len(pdf_bytes)} bytes)"
            )
            _log_test_message(phone, customer_msg)
            for name, mp in manager_phones:
                _log_test_message(mp, f"[Manager Copy – {name}]\n{customer_msg}")
            return {"success": True, "mode": "TEST", "phone": phone, "filename": filename}

        media_id = _upload_whatsapp_media(pdf_bytes, filename)
        if not media_id:
            return {"success": False, "error": "Media upload failed"}

        # Send to customer
        result = _send_whatsapp_template_with_document(phone, "holiday_order_form_pdf", media_id, filename, template_params)

        # Send same template+PDF to every manager
        for name, mp in manager_phones:
            try:
                _send_whatsapp_template_with_document(mp, "holiday_order_form_pdf", media_id, filename, template_params)
                logger.info(f"[WhatsApp] Manager copy sent to {name} (+{mp})")
            except Exception as me:
                logger.error(f"[WhatsApp] Manager copy failed for {name} (+{mp}): {me}")

        return result

    except Exception as e:
        logger.error(f"send_holiday_orderform_whatsapp error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def send_holiday_orderform_whatsapp_managers(booking) -> dict:
    """
    Send the holiday order form PDF only to all managers (used for Resend to Managers).
    """
    from .models import WhatsAppConfig
    if not WhatsAppConfig.get_config().holiday_enabled:
        return {"success": False, "error": "Holiday WhatsApp notifications are disabled"}
    try:
        from .holiday_views import number_to_words
        company = booking.company
        manager_phones = _get_manager_phones(company)
        if not manager_phones:
            return {"success": False, "error": "No managers found for this company."}

        context = {
            "booking": booking,
            "company": company,
            "balance_in_words": number_to_words(booking.balance_amount or 0),
        }
        pdf_bytes = _generate_pdf("vouchers/holiday_print.html", context, company=company)
        filename  = f"Order_Form_{booking.booking_number}.pdf"

        if not WHATSAPP_LIVE_MODE:
            print(f"\n{'='*60}")
            print(f"[WhatsApp PDF TEST] Holiday Order Form – Managers Resend")
            print(f"  File     : {filename}")
            print(f"  PDF size : {len(pdf_bytes)} bytes")
            for name, mp in manager_phones:
                print(f"  To       : +{mp}  [{name}]")
            print(f"{'='*60}\n")
            return {"success": True, "mode": "TEST", "managers_notified": len(manager_phones)}

        media_id = _upload_whatsapp_media(pdf_bytes, filename)
        if not media_id:
            return {"success": False, "error": "Media upload failed"}

        caption = f"Holiday Booking – {booking.booking_number}"
        sent, failed = 0, 0
        for name, mp in manager_phones:
            try:
                r = _send_whatsapp_document(mp, media_id, filename, caption=caption)
                if r.get('success'):
                    sent += 1
                    logger.info(f"[WhatsApp] Manager resend sent to {name} (+{mp})")
                else:
                    failed += 1
                    logger.error(f"[WhatsApp] Manager resend failed for {name}: {r.get('error')}")
            except Exception as me:
                failed += 1
                logger.error(f"[WhatsApp] Manager resend exception for {name} (+{mp}): {me}")

        if sent == 0:
            return {"success": False, "error": f"All {failed} sends failed."}
        return {"success": True, "managers_notified": sent, "failed": failed}

    except Exception as e:
        logger.error(f"send_holiday_orderform_whatsapp_managers error: {e}", exc_info=True)
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
