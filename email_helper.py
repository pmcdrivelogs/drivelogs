import os
import ssl
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _get_smtp_config():
    host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.getenv('SMTP_PORT', '587'))
    user = os.getenv('SMTP_USER')
    password = os.getenv('SMTP_PASSWORD')
    return host, port, user, password


def _normalize_recipients(to_addrs):
    if to_addrs is None:
        env_to = os.getenv('EMAIL_TO') or os.getenv('ADMIN_EMAIL')
        if not env_to:
            return []
        to_addrs = env_to
    if isinstance(to_addrs, str):
        return [x.strip() for x in to_addrs.split(',') if x.strip()]
    return list(to_addrs)


def send_email(subject, body, to_addrs=None, html=False, from_addr=None):
    """Send an email using SMTP settings from environment.

    Required env vars for sending:
      - SMTP_USER, SMTP_PASSWORD
    Optional:
      - SMTP_HOST (default smtp.gmail.com)
      - SMTP_PORT (default 587)
      - EMAIL_FROM (defaults to SMTP_USER)
      - EMAIL_TO (comma-separated fallback recipients)
    """
    host, port, user, password = _get_smtp_config()
    to = _normalize_recipients(to_addrs)
    if not user or not password or not to:
        logger.warning('SMTP_USER, SMTP_PASSWORD or EMAIL_TO not configured — skipping email send')
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    from_addr = from_addr or os.getenv('EMAIL_FROM') or user
    msg['From'] = from_addr
    msg['To'] = ', '.join(to)

    if html:
        msg.add_alternative(body, subtype='html')
    else:
        msg.set_content(body)

    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(user, password)
                server.send_message(msg)
        logger.info('Email sent to %s subject=%s', to, subject)
        return True
    except Exception as e:
        logger.exception('Failed to send email: %s', e)
        return False


def format_vehicle_reminder(vehicle, field_label, days_left, due_date_iso=None):
    reg = vehicle.get('registration_no') or vehicle.get('vehicle_id') or 'Unknown'
    subject = f"Reminder: {reg} — {field_label} expires in {days_left} day(s)"
    lines = [f"Vehicle: {reg}", f"Vehicle ID: {vehicle.get('vehicle_id', '')}", f"Due field: {field_label}"]
    if due_date_iso:
        lines.append(f"Due date: {due_date_iso}")
    lines.append(f"Days remaining: {days_left}")
    # include some common fields for context
    for k in ('insurance_company', 'make', 'model'):
        v = vehicle.get(k)
        if v:
            lines.append(f"{k.replace('_', ' ').title()}: {v}")

    body = "\n".join(lines)
    return subject, body
