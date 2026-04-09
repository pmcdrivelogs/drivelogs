import os
import json
from datetime import date, datetime
from dateutil import parser as date_parser
import logging

from email_helper import send_email, format_vehicle_reminder
from database import get_all_vehicles, get_all_statutory_records

logger = logging.getLogger(__name__)

# Fields to watch on vehicle rows -> human label
VEHICLE_DATE_FIELDS = {
    'fitness_validity': 'Fitness Validity',
    'insurance_validity': 'Insurance Validity',
    'registration_validity': 'Registration Validity',
    'permit_validity': 'Permit Validity',
    'pucc_validity': 'PUCC Validity',
    'tax_validity': 'Tax Validity'
}

# Human-readable labels for vehicle validity fields used in statutory alerts
_STATUTORY_FIELD_LABELS = {
    'fitness_validity': 'Fitness Certificate',
    'insurance_validity': 'Insurance',
    'registration_validity': 'Registration',
    'permit_validity': 'Permit',
    'pucc_validity': 'Pollution Certificate',
    'tax_validity': 'Road Tax',
}

LOG_FILE = os.path.join(os.path.dirname(__file__), 'email_sent_log.json')
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'reminder_settings.json')


def _load_log():
    try:
        if not os.path.exists(LOG_FILE):
            return {}
        with open(LOG_FILE, 'r', encoding='utf-8') as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _save_log(log):
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as fh:
            json.dump(log, fh, indent=2, default=str)
    except Exception:
        logger.exception('Failed to save email sent log')


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    s = str(val).strip()
    try:
        # Try direct YYYY-MM-DD fragment
        if len(s) >= 10 and s[4] == '-' and s[7] == '-':
            return datetime.strptime(s.split('T')[0].split(' ')[0], '%Y-%m-%d').date()
    except Exception:
        pass
    try:
        return date_parser.parse(s).date()
    except Exception:
        return None


def _already_sent_today(log, vehicle_id, field_key, ts_date):
    day_key = ts_date.isoformat()
    items = log.get(day_key, [])
    for it in items:
        if it.get('vehicle_id') == vehicle_id and it.get('field') == field_key:
            return True
    return False


def _mark_sent(log, vehicle_id, field_key, ts_date, info=None):
    day_key = ts_date.isoformat()
    items = log.setdefault(day_key, [])
    items.append({'vehicle_id': vehicle_id, 'field': field_key, 'ts': datetime.utcnow().isoformat(), 'info': info or {}})


def get_settings():
    """Load reminder settings from JSON file. Returns a dict with defaults."""
    try:
        if not os.path.exists(SETTINGS_FILE):
            return {
                'recipients': None,
                'enabled': True,
                'immediate_enabled': True,
                'reminder_days': 30,
                'reminder_hour': 9,
                'reminder_minute': 0
            }
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh) or {}
            # ensure defaults
            return {
                'recipients': data.get('recipients') or None,
                'enabled': bool(data.get('enabled', True)),
                'immediate_enabled': bool(data.get('immediate_enabled', True)),
                'reminder_days': int(data.get('reminder_days', 30)),
                'reminder_hour': int(data.get('reminder_hour', 9)),
                'reminder_minute': int(data.get('reminder_minute', 0))
            }
    except Exception:
        logger.exception('Failed to load reminder settings')
        return {
            'recipients': None,
            'enabled': True,
            'immediate_enabled': True,
            'reminder_days': 30,
            'reminder_hour': 9,
            'reminder_minute': 0
        }


def save_settings(data: dict):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2, default=str)
        return True
    except Exception:
        logger.exception('Failed to save reminder settings')
        return False


def check_and_send_validity_reminders(reminder_days=None):
    """Scan vehicle validity dates and send reminder emails for items due within `reminder_days`.

    Uses env vars:
      - EMAIL_TO: comma-separated recipients (required)
      - REMINDER_DAYS: integer (default 15)
    """
    # load runtime settings (overrides env)
    settings = get_settings() or {}
    if not settings.get('enabled', True):
        logger.info('Reminders disabled by settings — skipping')
        return

    try:
        reminder_days = int(reminder_days or settings.get('reminder_days') or os.getenv('REMINDER_DAYS', '30'))
    except Exception:
        reminder_days = 15

    recipients = settings.get('recipients') or os.getenv('EMAIL_TO') or os.getenv('ADMIN_EMAIL')
    if not recipients:
        logger.warning('No recipients configured (settings or EMAIL_TO) — skipping reminders')
        return

    today = date.today()
    log = _load_log()
    vehicles = []
    try:
        vehicles = get_all_vehicles() or []
    except Exception:
        logger.exception('Failed to load vehicles for reminders')

    sends = 0
    for v in vehicles:
        vid = v.get('vehicle_id') or v.get('id') or v.get('registration_no')
        for field_key, label in VEHICLE_DATE_FIELDS.items():
            raw = v.get(field_key)
            parsed = _parse_date(raw)
            if not parsed:
                continue
            days_left = (parsed - today).days
            if 0 <= days_left <= reminder_days:
                if _already_sent_today(log, str(vid), field_key, today):
                    logger.debug('Reminder already sent today for %s %s', vid, field_key)
                    continue
                subject, body = format_vehicle_reminder(v, label, days_left, due_date_iso=parsed.isoformat())
                ok = send_email(subject, body, to_addrs=recipients)
                if ok:
                    _mark_sent(log, str(vid), field_key, today, info={'days_left': days_left})
                    sends += 1
                else:
                    logger.warning('Failed to send reminder for %s %s', vid, field_key)

    if sends:
        _save_log(log)
    logger.info('Validity reminders run complete — emails sent: %d', sends)


def _collect_statutory_alerts(reminder_days=30):
    """Return a list of alert dicts for all statutory/vehicle records expiring within reminder_days (or overdue)."""
    today = date.today()
    alerts = []

    # 1. Statutory table records
    try:
        records = get_all_statutory_records() or []
    except Exception:
        records = []

    for rec in records:
        raw = rec.get('validity_date')
        if not raw:
            continue
        parsed = _parse_date(raw)
        if not parsed:
            continue
        days_left = (parsed - today).days
        if days_left <= reminder_days:
            alerts.append({
                'record_type': rec.get('type_of_transaction', 'Statutory'),
                'vehicle_id': rec.get('vehicle_id') or rec.get('statutory_body_id') or 'Unknown',
                'registration_no': rec.get('registration_no') or 'N/A',
                'next_due': parsed.strftime('%d-%m-%Y'),
                'days_remaining': days_left,
                'status': 'OVERDUE' if days_left < 0 else 'DUE SOON',
            })

    # 2. Vehicle-level validity date fields
    try:
        vehicles = get_all_vehicles() or []
    except Exception:
        vehicles = []

    for v in vehicles:
        vid = v.get('vehicle_id') or v.get('id') or 'Unknown'
        reg = v.get('registration_no') or v.get('registration') or 'N/A'
        for field_key, label in _STATUTORY_FIELD_LABELS.items():
            raw = v.get(field_key)
            if not raw:
                continue
            parsed = _parse_date(raw)
            if not parsed:
                continue
            days_left = (parsed - today).days
            if days_left <= reminder_days:
                alerts.append({
                    'record_type': label,
                    'vehicle_id': vid,
                    'registration_no': reg,
                    'next_due': parsed.strftime('%d-%m-%Y'),
                    'days_remaining': days_left,
                    'status': 'OVERDUE' if days_left < 0 else 'DUE SOON',
                })

    alerts.sort(key=lambda x: x['days_remaining'])
    return alerts


def send_statutory_alerts_email(reminder_days=None):
    """Collect all statutory/vehicle expiry alerts and send a single summary email."""
    settings = get_settings() or {}
    if not settings.get('enabled', True):
        logger.info('Reminders disabled by settings — skipping statutory alert email')
        return

    try:
        reminder_days = int(reminder_days or settings.get('reminder_days') or os.getenv('REMINDER_DAYS', '30'))
    except Exception:
        reminder_days = 30

    recipients = settings.get('recipients') or os.getenv('EMAIL_TO') or os.getenv('ADMIN_EMAIL')
    if not recipients:
        logger.warning('No recipients configured — skipping statutory alert email')
        return

    alerts = _collect_statutory_alerts(reminder_days)
    if not alerts:
        logger.info('No statutory alerts to send today')
        return

    today_str = date.today().strftime('%d-%m-%Y')
    subject = f'Statutory Records Alert — {today_str} ({len(alerts)} item(s))'

    # Plain-text body
    lines = [
        f'Statutory Records Alert — {today_str}',
        f'Records expiring within {reminder_days} days (or already overdue)',
        '',
        f'{"Type":<28} {"Vehicle ID":<12} {"Reg No":<16} {"Next Due":<14} {"Status"}',
        '-' * 90,
    ]
    for a in alerts:
        lines.append(
            f'{a["record_type"]:<28} {str(a["vehicle_id"]):<12} {a["registration_no"]:<16} '
            f'{a["next_due"]:<14} {a["status"]}'
        )
    lines += ['', f'Total: {len(alerts)} record(s)', '-- Drive Logs Reminder System']
    plain_body = '\n'.join(lines)

    # HTML body with a styled table matching the dashboard popup look
    rows_html = ''
    for a in alerts:
        badge_class = 'background:#e53e3e;color:#fff;' if a['status'] == 'OVERDUE' else 'background:#dd6b20;color:#fff;'
        rows_html += (
            f'<tr>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{a["record_type"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{a["vehicle_id"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{a["registration_no"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{a["next_due"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">'
            f'<span style="padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;{badge_class}">'
            f'{a["status"]}</span></td>'
            f'</tr>'
        )

    html_body = f"""
<html><body style="font-family:Arial,sans-serif;background:#f7fafc;padding:24px;">
  <div style="max-width:700px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);">
    <div style="background:#3730a3;color:#fff;padding:20px 24px;">
      <h2 style="margin:0;font-size:20px;">&#9888; Statutory Records Alert</h2>
      <p style="margin:4px 0 0;font-size:14px;">Records expiring within {reminder_days} days &mdash; {today_str}</p>
    </div>
    <div style="padding:20px 24px;">
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#edf2f7;">
            <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e2e8f0;">Type</th>
            <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e2e8f0;">Vehicle ID</th>
            <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e2e8f0;">Reg No</th>
            <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e2e8f0;">Next Due</th>
            <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e2e8f0;">Status</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="margin-top:16px;font-size:13px;color:#718096;">Total: {len(alerts)} record(s) &mdash; Drive Logs Reminder System</p>
    </div>
  </div>
</body></html>
"""

    ok = send_email(subject, html_body, to_addrs=recipients, html=True)
    if ok:
        logger.info('Statutory alert email sent to %s (%d alerts)', recipients, len(alerts))
    else:
        # fallback to plain text
        ok = send_email(subject, plain_body, to_addrs=recipients, html=False)
        logger.info('Statutory alert email (plain) sent: %s', ok)


def start_scheduler(app=None):
    """Start a background scheduler to run the reminders daily.

    Schedules a daily job at hour/minute defined by REMINDER_HOUR/REMINDER_MINUTE (defaults 07:00).
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception:
        # APScheduler or its dependency `pkg_resources` (setuptools) may be missing.
        # Log a concise warning (no stacktrace) and skip starting the scheduler.
        logger.warning('APScheduler unavailable; reminders scheduler disabled')
        return None

    hour = os.getenv('REMINDER_HOUR', '9')
    minute = os.getenv('REMINDER_MINUTE', '0')

    scheduler = BackgroundScheduler()
    try:
        scheduler.add_job(lambda: check_and_send_validity_reminders(), 'cron', hour=hour, minute=minute)
        scheduler.add_job(lambda: send_statutory_alerts_email(), 'cron', hour=hour, minute=minute, id='statutory_alerts_daily')
        scheduler.start()
        logger.info('Started reminders scheduler (daily at %s:%s) — validity + statutory alerts', hour, minute)
        if app is not None:
            try:
                app.extensions = getattr(app, 'extensions', {})
                app.extensions['reminder_scheduler'] = scheduler
            except Exception:
                pass
        return scheduler
    except Exception:
        logger.exception('Failed to start reminders scheduler')
        return None


if __name__ == '__main__':
    # allow running ad-hoc
    check_and_send_validity_reminders()
    send_statutory_alerts_email()
