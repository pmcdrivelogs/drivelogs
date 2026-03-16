import os
import json
from datetime import date, datetime
from dateutil import parser as date_parser
import logging

from email_helper import send_email, format_vehicle_reminder
from database import get_all_vehicles

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
                'reminder_days': 15,
                'reminder_hour': 7,
                'reminder_minute': 0
            }
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh) or {}
            # ensure defaults
            return {
                'recipients': data.get('recipients') or None,
                'enabled': bool(data.get('enabled', True)),
                'immediate_enabled': bool(data.get('immediate_enabled', True)),
                'reminder_days': int(data.get('reminder_days', 15)),
                'reminder_hour': int(data.get('reminder_hour', 7)),
                'reminder_minute': int(data.get('reminder_minute', 0))
            }
    except Exception:
        logger.exception('Failed to load reminder settings')
        return {
            'recipients': None,
            'enabled': True,
            'immediate_enabled': True,
            'reminder_days': 15,
            'reminder_hour': 7,
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
        reminder_days = int(reminder_days or settings.get('reminder_days') or os.getenv('REMINDER_DAYS', '15'))
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


def start_scheduler(app=None):
    """Start a background scheduler to run the reminders daily.

    Schedules a daily job at hour/minute defined by REMINDER_HOUR/REMINDER_MINUTE (defaults 07:00).
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception:
        logger.exception('APScheduler not installed; cannot start reminders scheduler')
        return None

    hour = os.getenv('REMINDER_HOUR', '7')
    minute = os.getenv('REMINDER_MINUTE', '0')

    scheduler = BackgroundScheduler()
    try:
        scheduler.add_job(lambda: check_and_send_validity_reminders(), 'cron', hour=hour, minute=minute)
        scheduler.start()
        logger.info('Started reminders scheduler (daily at %s:%s)', hour, minute)
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
