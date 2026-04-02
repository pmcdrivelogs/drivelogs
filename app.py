import pkgutil
import importlib.util

# Compatibility shim: Python 3.12+ removed `pkgutil.get_loader` which
# older Flask versions call. Provide a minimal replacement that returns
# an object with `get_filename()` so Flask can determine package paths.
if not hasattr(pkgutil, "get_loader"):
    def _get_loader(name):
        # Avoid inspecting __main__ (find_spec may raise ValueError)
        if name == "__main__":
            return None
        try:
            spec = importlib.util.find_spec(name)
        except Exception:
            return None
        if spec is None:
            return None
        class _Loader:
            def get_filename(self, fullname):
                return spec.origin
        return _Loader()
    pkgutil.get_loader = _get_loader

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
import os
import logging
from collections import deque
from database import (
    authenticate_user, authenticate_super_admin, log_login_attempt, 
    save_vehicle_annual_record, get_vehicle_annual_record, 
    save_vehicle_permanent_record, get_vehicle_permanent_record, 
    save_trip_opening_checklist, save_utilization_record, save_fuel_consumption, 
    save_daily_technical_remarks, save_weekly_attention, save_driver_voice, 
    save_technician_observation_works, save_technician_observation_materials, 
    save_process_of_works, save_monthly_maintenance, save_halfyearly_maintenance, 
    save_annual_maintenance, save_annual_summary_complaints, save_annual_summary_recommendations, 
    save_incidents_reports_incidents, save_incidents_reports_claims, save_feedback,
    get_next_accident_entry_no, save_accident_incident,
    get_all_accidents_incidents, get_accident_incident_by_id,
    save_purchase, get_next_purchase_entry_no,
    save_fuel, get_next_fuel_entry_no,
    save_stock, get_next_stock_entry_no,
    save_statutory, get_next_statutory_entry_no,
    get_all_users, get_all_vehicles, get_users_count, get_vehicles_count,
    get_user_by_id, get_vehicle_by_id, admin_create_user, admin_update_user,
    get_vehicle_by_vehicle_id,
    admin_delete_user, admin_toggle_user_status, admin_add_vehicle, admin_update_vehicle,
    admin_delete_vehicle, get_all_fuel_records, get_all_statutory_records, 
    get_all_trip_sheets, get_all_purchases, get_all_stock_issues, get_all_utilization, 
    get_all_scrap, get_stock_totals, save_maintenance_entry, update_maintenance_entry, supabase
)
from database import save_dc_entry, get_all_dc_entries, get_dc_entry, get_last_dc_save_error, _get_next_dc_number
from database import save_material_utilization, consume_part_from_purchases
from datetime import datetime
import time
import json
from dotenv import load_dotenv

load_dotenv()

# Email helper for immediate notifications
from email_helper import send_email, format_vehicle_reminder
# Reminder settings API
from reminders import get_settings, save_settings

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Disable template caching for development
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Jinja filter: format datetime strings to DD/MM/YYYY or DD/MM/YYYY HH:MM when time present
def _format_date(value, with_time=False):
    if not value:
        return ''
    try:
        # If it's already a datetime
        if hasattr(value, 'strftime'):
            dt = value
        else:
            s = str(value)
            # Handle common ISO formats
            try:
                # fromisoformat supports 'YYYY-MM-DD' and 'YYYY-MM-DDTHH:MM:SS'
                dt = datetime.fromisoformat(s)
            except Exception:
                # try common other formats
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
                    try:
                        dt = datetime.strptime(s, fmt)
                        break
                    except Exception:
                        dt = None
                if dt is None:
                    # fallback: return raw string
                    return s
        if with_time:
            return dt.strftime('%d/%m/%Y %H:%M')
        return dt.strftime('%d/%m/%Y')
    except Exception:
        try:
            return str(value)
        except Exception:
            return ''

# Register the filter
app.jinja_env.filters['fmt_dt'] = _format_date

# Fields to watch on admin vehicle edits for immediate notifications
VEHICLE_DATE_FIELDS = {
    # Map vehicle date fields to the normalized statutory type names
    'fitness_validity': 'Fitness Certificate',
    'insurance_validity': 'Insurance',
    'registration_validity': 'Registration',
    'permit_validity': 'Permit',
    'pucc_validity': 'Pollution Certificate',
    'tax_validity': 'Road Tax'
}


def parse_date_str(dt_string):
    """Parse a variety of date-like strings into a date object.
    Returns a datetime.date or None if parsing fails.
    """
    if not dt_string:
        return None
    s = str(dt_string).strip()
    try:
        # Handle ISO-like strings first (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        if 'T' in s:
            s_date = s.split('T')[0]
            return datetime.fromisoformat(s_date).date()
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            # fallback to common YYYY-MM-DD pattern
            try:
                return datetime.strptime(s.split(' ')[0], '%Y-%m-%d').date()
            except Exception:
                pass
    except Exception:
        pass

    # Try extracting a YYYY-MM-DD fragment with regex
    try:
        import re as _re
        m = _re.search(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            return datetime.strptime(m.group(1), '%Y-%m-%d').date()
    except Exception:
        pass

    # Last resort: try dateutil if available
    try:
        from dateutil import parser as date_parser
        return date_parser.parse(s).date()
    except Exception:
        return None

# In-memory log buffer for recent application logs (temporary, for debugging)
LOG_BUFFER = deque(maxlen=400)

class BufferHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        LOG_BUFFER.append({'level': record.levelname, 'message': msg, 'time': record.created})

# Attach buffer handler to app logger
buffer_handler = BufferHandler()
buffer_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
buffer_handler.setFormatter(formatter)
app.logger.addHandler(buffer_handler)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Login required decorator (allows both user and admin)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session and 'admin' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def module_required(module_name):
    """Decorator to restrict access to users who have the given module assigned.
    Super-admins (session 'admin') are allowed by default.
    """
    def _decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Super admin bypass
            if 'admin' in session:
                return f(*args, **kwargs)

            uid = session.get('user_id')
            try:
                if not uid:
                    flash('Access denied: not authorized', 'danger')
                    return redirect(url_for('dashboard'))
                user = get_user_by_id(uid)
                mods = user.get('modules') if user else None
                if not mods:
                    flash('Access denied: module not assigned', 'danger')
                    return redirect(url_for('dashboard'))
                # Allow if module present
                if module_name in mods:
                    return f(*args, **kwargs)
                flash('Access denied: you do not have permissions for this module', 'danger')
                return redirect(url_for('dashboard'))
            except Exception:
                flash('Access denied: error checking permissions', 'danger')
                return redirect(url_for('dashboard'))
        return wrapped
    return _decorator

# Admin login required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            flash('Admin access required', 'danger')
            return redirect(url_for('super_admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Authenticate with Supabase
        user = authenticate_user(email, password)
        
        if user:
            session['user'] = email
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            flash('Login successful!', 'success')
            log_login_attempt(email, True, request.remote_addr)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
            log_login_attempt(email, False, request.remote_addr)
    
    return render_template('login.html')

@app.route('/super-admin-login', methods=['GET', 'POST'])
def super_admin_login():
    if request.method == 'POST':
        identifier = request.form.get('email')  # Can be email or username
        password = request.form.get('password')
        
        # Authenticate with Supabase
        admin = authenticate_super_admin(identifier, password)
        
        if admin:
            session['admin'] = identifier
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['full_name']
            flash('Admin login successful!', 'success')
            log_login_attempt(identifier, True, request.remote_addr)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'danger')
            log_login_attempt(identifier, False, request.remote_addr)
    
    return render_template('super_admin_login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Fetch current user's assigned modules (if any) and pass to template
    user_modules = []
    due_soon_alerts = []
    try:
        uid = session.get('user_id')
        if uid:
            u = get_user_by_id(uid)
            if u:
                user_modules = u.get('modules') or []
    except Exception:
        user_modules = []

    # Build statutory alerts for user dashboard popup (same behavior as admin dashboard).
    try:
        today = datetime.now().date()
        statutory_records = get_all_statutory_records() or []
        for record in statutory_records:
            raw_validity = record.get('validity_date')
            if not raw_validity:
                continue
            try:
                validity_date_str = str(raw_validity)
                if 'T' in validity_date_str:
                    validity_date = datetime.fromisoformat(validity_date_str.split('T')[0]).date()
                else:
                    validity_date = datetime.strptime(validity_date_str.split(' ')[0], '%Y-%m-%d').date()

                days_remaining = (validity_date - today).days
                if days_remaining <= 7:
                    vehicle_id = record.get('vehicle_id') or record.get('statutory_body_id') or 'Unknown'
                    registration_no = record.get('registration_no') or 'N/A'
                    due_soon_alerts.append({
                        'statutory_body_id': record.get('statutory_body_id', 'Unknown'),
                        'vehicle_id': vehicle_id,
                        'registration_no': registration_no,
                        'record_type': record.get('type_of_transaction', 'Statutory'),
                        'next_due': validity_date.strftime('%d-%m-%Y'),
                        'days_remaining': days_remaining,
                        'alert_type': 'overdue' if days_remaining < 0 else 'warning'
                    })
            except Exception:
                continue
        due_soon_alerts.sort(key=lambda x: x['days_remaining'])
    except Exception:
        due_soon_alerts = []

    return render_template('dashboard.html', modules=user_modules, due_soon_alerts=due_soon_alerts)


@app.route('/dc-gate-pass', methods=['GET', 'POST'])
@login_required
@module_required('DC')
def dc_gate_pass():
    """Render and submit DC/Gate Pass format page."""
    header = {
        'dc_no': '',
        'to_name': '',
        'pin': '',
        'phone_no': '',
        'date': '',
        'person_carry': '',
        'person_id_no': '',
        'person_organization': '',
        'vehicle_reg_no': '',
        'driver_name': '',
        'driver_phone': ''
    }
    rows = [
        {'sl_no': '', 'part_no': '', 'ref_no': '', 'particulars': '', 'qty': '', 'reason': '', 'return_date': '', 'return_status': '', 'remarks': ''}
        for _ in range(4)
    ]
    submitted = False

    # On GET, prefill the next DC number so users see the upcoming Entry No
    try:
        next_num = _get_next_dc_number()
        if next_num:
            header['dc_no'] = 'PMC/LOGI/DC/' + str(next_num).zfill(3)
    except Exception:
        # leave header.dc_no empty to fallback to template default
        pass

    if request.method == 'POST':
        submitted = True
        for key in header:
            header[key] = request.form.get(key, '')
        # Always assign a fresh DC number on save so every submit increments.
        header['dc_no'] = ''

        sl_nos = request.form.getlist('sl_no[]')
        part_nos = request.form.getlist('part_no[]')
        ref_nos = request.form.getlist('ref_no[]')
        particulars = request.form.getlist('particulars[]')
        qtys = request.form.getlist('qty[]')
        reasons = request.form.getlist('reason[]')
        return_dates = request.form.getlist('return_date[]')
        return_statuses = request.form.getlist('return_status[]')
        remarks = request.form.getlist('remarks[]')

        max_len = max(
            len(sl_nos), len(part_nos), len(ref_nos), len(particulars), len(qtys),
            len(reasons), len(return_dates), len(return_statuses), len(remarks), 4
        )

        rows = []
        for idx in range(max_len):
            rows.append({
                'sl_no': sl_nos[idx] if idx < len(sl_nos) else '',
                'part_no': part_nos[idx] if idx < len(part_nos) else '',
                'ref_no': ref_nos[idx] if idx < len(ref_nos) else '',
                'particulars': particulars[idx] if idx < len(particulars) else '',
                'qty': qtys[idx] if idx < len(qtys) else '',
                'reason': reasons[idx] if idx < len(reasons) else '',
                'return_date': return_dates[idx] if idx < len(return_dates) else '',
                'return_status': return_statuses[idx] if idx < len(return_statuses) else '',
                'remarks': remarks[idx] if idx < len(remarks) else ''
            })
        # Server-side validation: ensure header.date and row return_date/sl_no are valid
        def _is_blank(val):
            return val is None or str(val).strip() == ''

        def _validate_date_str(s):
            if _is_blank(s):
                return True
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    datetime.strptime(str(s).strip(), fmt)
                    return True
                except Exception:
                    continue
            return False

        # Validate header date
        if not _validate_date_str(header.get('date')):
            flash('Header date must be YYYY-MM-DD (or leave blank).', 'danger')
            return render_template('dc_gate_pass.html', header=header, rows=rows, submitted=False)

        # Validate each row's return_date and sl_no
        for i, r in enumerate(rows, start=1):
            if not _validate_date_str(r.get('return_date')):
                flash(f'Row {i}: Return date must be YYYY-MM-DD (or leave blank).', 'danger')
                return render_template('dc_gate_pass.html', header=header, rows=rows, submitted=False)
            sl = r.get('sl_no')
            if not _is_blank(sl):
                try:
                    int(str(sl).strip())
                except Exception:
                    flash(f'Row {i}: Sl no must be an integer (or leave blank).', 'danger')
                    return render_template('dc_gate_pass.html', header=header, rows=rows, submitted=False)

        # Persist to DB (if Supabase configured)
        try:
            saved = save_dc_entry(header, rows, session.get('user_id'))
            if saved:
                # update header.dc_no with assigned value from DB
                header['dc_no'] = saved.get('dc_no') or header.get('dc_no')
                flash('DC saved to history.', 'success')
                # After successful submit, redirect to history
                return redirect(url_for('dc_history'))
            reason = get_last_dc_save_error() or 'Unknown database error while saving DC.'
            flash(f'Failed to save DC. {reason}', 'danger')
        except Exception as e:
            app.logger.exception('Failed to save DC entry: %s', e)
            flash(f'Warning: failed to save DC history. {str(e)}', 'warning')

    return render_template('dc_gate_pass.html', header=header, rows=rows, submitted=submitted)


@app.route('/dc-history')
@login_required
@module_required('DC')
def dc_history():
    """Show recent DC entries (history)."""
    entries = []
    try:
        entries = get_all_dc_entries()
    except Exception as e:
        app.logger.exception('Error fetching DC history: %s', e)
        flash('Unable to load DC history', 'warning')
    return render_template('dc_history.html', entries=entries)


@app.route('/dc-view/<entry_id>')
@login_required
@module_required('DC')
def dc_view(entry_id):
    # entry_id may be an integer id or a string UUID depending on backend
    data = get_dc_entry(entry_id)
    if not data:
        flash('DC entry not found', 'danger')
        return redirect(url_for('dc_history'))

    # Map DB row items to expected template rows structure
    header = data.get('header') or {}
    rows = []
    for it in data.get('rows', []):
        rows.append({
            'sl_no': it.get('sl_no'),
            'part_no': it.get('part_no'),
            'ref_no': it.get('ref_no'),
            'particulars': it.get('particulars'),
            'qty': it.get('qty'),
            'reason': it.get('reason'),
            'return_date': it.get('return_date'),
            'return_status': it.get('return_status'),
            'remarks': it.get('remarks')
        })

    return render_template('dc_gate_pass.html', header=header, rows=rows, submitted=True, view_only=True)


@app.route('/dc-view')
@login_required
@module_required('DC')
def dc_view_query():
    # Support query-parameter lookups: /dc-view?id=123 or /dc-view?dc_no=PMC/LOGI/DC/001
    entry_id = request.args.get('id') or request.args.get('dc_no')
    if not entry_id:
        flash('DC entry not specified', 'danger')
        return redirect(url_for('dc_history'))

    data = get_dc_entry(entry_id)
    if not data:
        flash('DC entry not found', 'danger')
        return redirect(url_for('dc_history'))

    header = data.get('header') or {}
    rows = []
    for it in data.get('rows', []):
        rows.append({
            'sl_no': it.get('sl_no'),
            'part_no': it.get('part_no'),
            'ref_no': it.get('ref_no'),
            'particulars': it.get('particulars'),
            'qty': it.get('qty'),
            'reason': it.get('reason'),
            'return_date': it.get('return_date'),
            'return_status': it.get('return_status'),
            'remarks': it.get('remarks')
        })

    return render_template('dc_gate_pass.html', header=header, rows=rows, submitted=True, view_only=True)



@app.route('/dc-items-json')
@login_required
def dc_items_json():
    """Return dc_items for a given entry as JSON (used by status modal)."""
    entry_id = request.args.get('entry_id')
    if not entry_id:
        return jsonify({'items': []})
    try:
        data = get_dc_entry(entry_id)
        items = []
        for it in (data.get('rows') or []) if data else []:
            items.append({
                'sl_no': it.get('sl_no') or '',
                'part_no': it.get('part_no') or '',
                'particulars': it.get('particulars') or '',
                'return_status': it.get('return_status') or '',
                'return_date': it.get('return_date') or '',
                'remarks': it.get('remarks') or '',
            })
        return jsonify({'items': items})
    except Exception as e:
        return jsonify({'items': [], 'error': str(e)})


@app.route('/dc-update-status', methods=['POST'])
@login_required
def dc_update_status():
    """AJAX endpoint to update a single dc_items row's return status, date and remarks."""
    try:
        data = request.get_json(force=True) or {}
        entry_id = data.get('entry_id')
        item_index = data.get('item_index', 0)
        status = data.get('status', '')
        return_date = data.get('return_date', '')
        remarks = data.get('remarks', '')
        if not entry_id or not status:
            return jsonify({'ok': False, 'error': 'entry_id and status are required'}), 400
        from database import update_dc_item_status
        ok, msg = update_dc_item_status(entry_id, int(item_index), status, return_date or None, remarks or None)
        return jsonify({'ok': ok, 'message': msg})
    except Exception as e:
        app.logger.exception('dc_update_status error: %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/dc-return-history')
@login_required
@module_required('DC')
def dc_return_history():
    """Show all dc_items with status Returnable."""
    from database import get_dc_items_by_status
    items = get_dc_items_by_status('Returnable')
    return render_template('dc_return_history.html', items=items, title='Return History', status_filter='Returnable')


@app.route('/dc-nonreturnable-history')
@login_required
@module_required('DC')
def dc_nonreturnable_history():
    """Show all dc_items with status Non-Returnable."""
    from database import get_dc_items_by_status
    items = get_dc_items_by_status('Non-Returnable')
    return render_template('dc_return_history.html', items=items, title='Non-Returnable History', status_filter='Non-Returnable')


@app.route('/_debug/logs')
@login_required
def debug_logs_json():
    """Return recent in-memory server logs for debugging (login required)."""
    try:
        # Return last buffered log messages (BufferHandler stores dicts)
        return jsonify(list(LOG_BUFFER))
    except Exception as e:
        app.logger.exception('Error returning debug logs: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/_debug/dc_list')
@login_required
def debug_dc_list():
    """Return last 20 dc_entries with a count of dc_items for quick inspection."""
    try:
        entries = get_all_dc_entries(limit=20)
        out = []
        for e in entries:
            eid = e.get('id')
            try:
                # ensure numeric id when possible
                qid = int(eid) if isinstance(eid, (str,)) and str(eid).isdigit() else eid
            except Exception:
                qid = eid
            try:
                items_res = supabase.table('dc_items').select('*').eq('dc_entry_id', qid).execute()
                items = items_res.data or []
            except Exception as ex:
                items = []
            out.append({'id': eid, 'dc_no': e.get('dc_no'), 'items_count': len(items)})
        return jsonify({'entries': out})
    except Exception as e:
        app.logger.exception('Error in debug_dc_list: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/_debug/dc_inspect/<entry_id>')
@login_required
def debug_dc_inspect(entry_id):
    """Return raw db rows for a dc entry and its items."""
    try:
        # try integer conversion
        try:
            qid = int(entry_id) if str(entry_id).isdigit() else entry_id
        except Exception:
            qid = entry_id

        e_res = supabase.table('dc_entries').select('*').eq('id', qid).execute()
        items_res = supabase.table('dc_items').select('*').eq('dc_entry_id', qid).execute()
        return jsonify({
            'entry_raw': e_res.data or [],
            'items_raw': items_res.data or []
        })
    except Exception as e:
        app.logger.exception('Error in debug_dc_inspect: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/maintenance-image', methods=['GET', 'POST'])
@login_required
@module_required('Maintenance')
def maintenance_image():
    """Render the maintenance entry form and handle submissions."""
    def get_next_entry_no():
        """Return the next entry_no in the sequence PMC/MAIN/NNN (zero-padded).
        Falls back to a timestamp-derived suffix on error.
        """
        try:
            res = supabase.table('maintenance_entry').select('entry_no').like('entry_no', 'PMC/MAIN/%').execute()
            rows = res.data if res.data else []
            maxn = 0
            for r in rows:
                en = r.get('entry_no') or ''
                parts = en.split('/')
                if len(parts) >= 3:
                    try:
                        n = int(parts[2])
                        if n > maxn:
                            maxn = n
                    except Exception:
                        continue
            return f"PMC/MAIN/{(maxn+1):03d}"
        except Exception:
            import time
            return f"PMC/MAIN/{int(time.time())%1000:03d}"
    if request.method == 'POST':
        try:
            # Build data dict from form
            # Accept vehicle_id as-is (vehicle ids can be alphanumeric like '96A')
            vehicle_id = request.form.get('vehicle_id') or None

            # parse current_km if provided
            try:
                _ck = request.form.get('current_km')
                current_km = int(_ck) if (_ck is not None and str(_ck).strip() != '') else None
            except Exception:
                current_km = None

            data = {
                'entry_no': request.form.get('entry_no') or get_next_entry_no(),
                'date_time': request.form.get('date_time'),
                'vehicle_id': vehicle_id,
                'current_km': current_km,
                'registration_no': request.form.get('registration_no'),
                'driver_incharge': request.form.get('driver_incharge'),
                'drivers_voice': request.form.get('drivers_voice'),
                'technician_alloted': request.form.get('technician_alloted'),
                'technician_observation': request.form.get('technician_observation'),
                'possible_ways': request.form.get('possible_ways'),
                'parts_required': request.form.get('parts_required'),
                'processed_by': session.get('user_id') or session.get('admin_id'),
                'approved': False,
                'created_by': session.get('user_id') or session.get('admin_id')
            }

            saved = save_maintenance_entry(data)
            if saved:
                flash('Maintenance job card created successfully!', 'success')
                return redirect(url_for('maintenance_history'))
            else:
                flash('Failed to save job card. Try again.', 'danger')
        except Exception as e:
            flash(f'Error saving job card: {str(e)}', 'danger')
            import traceback
            traceback.print_exc()

    # GET: render form with vehicles for dropdown
    try:
        vehicles_res = supabase.table('vehicles').select('vehicle_id, registration_no').order('vehicle_id').execute()
        vehicles = vehicles_res.data if vehicles_res.data else []
    except Exception as e:
        vehicles = []

    return render_template('maintenance_image.html', vehicles=vehicles)


@app.route('/internal-audit', methods=['GET', 'POST'])
@login_required
@module_required('Internal Audit')
def internal_audit():
    """Simple Internal Audit report form (starter implementation)."""
    if request.method == 'POST':
        try:
            # TODO: persist audit data to DB (not implemented yet)
            flash('Internal audit submitted (stub).', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            app.logger.exception('Failed submitting internal audit')
            flash('Failed to submit audit: ' + str(e), 'danger')

    try:
        vehicles_res = supabase.table('vehicles').select('vehicle_id, registration_no').order('vehicle_id').execute()
        vehicles = vehicles_res.data if vehicles_res.data else []
    except Exception:
        vehicles = []
    try:
        employees_res = supabase.table('employees').select('employee_id, name').order('employee_id').execute()
        employees = employees_res.data if employees_res.data else []
    except Exception:
        employees = []

    return render_template('internal_audit.html', vehicles=vehicles, employees=employees)


@app.route('/api/employees', methods=['GET'])
@login_required
def api_employees_list():
    """Return a lightweight list of employees (id + name) for client-side datalists and search.
    """
    try:
        res = supabase.table('employees').select('employee_id, name, full_name').order('employee_id').execute()
        rows = res.data if res.data else []
        # normalize to minimal shape
        out = []
        for r in rows:
            emp_id = r.get('employee_id') or r.get('id') or ''
            name = r.get('name') or r.get('full_name') or ''
            out.append({'employee_id': emp_id, 'name': name})
        return jsonify({'success': True, 'employees': out}), 200
    except Exception as e:
        app.logger.exception('Failed to fetch employees list')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/employee/<path:employee_id>', methods=['GET'])
@login_required
def api_employee_get(employee_id):
    """Return a single employee row by employee_id (supports slashes).
    """
    try:
        # try to match by employee_id field
        res = supabase.table('employees').select('*').eq('employee_id', employee_id).limit(1).execute()
        row = None
        if res.data and len(res.data) > 0:
            row = res.data[0]
        else:
            # fallback: try matching against id if numeric
            try:
                res2 = supabase.table('employees').select('*').eq('id', int(employee_id)).limit(1).execute()
                if res2.data and len(res2.data) > 0:
                    row = res2.data[0]
            except Exception:
                pass

        if row:
            return jsonify({'success': True, 'employee': row}), 200
        return jsonify({'success': False, 'message': 'Not found'}), 404
    except Exception as e:
        app.logger.exception('Failed to fetch employee %s', employee_id)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/maintenance', methods=['POST'])
@login_required
def api_create_maintenance():
    """API endpoint to create a maintenance entry and return JSON (used by AJAX)."""
    try:
        # Accept vehicle_id as-is (some vehicle ids are alphanumeric)
        vehicle_id = request.form.get('vehicle_id') or None

        # compute next entry number in the desired sequence
        def get_next_entry_no_api():
            try:
                res = supabase.table('maintenance_entry').select('entry_no').like('entry_no', 'PMC/MAIN/%').execute()
                rows = res.data if res.data else []
                maxn = 0
                for r in rows:
                    en = r.get('entry_no') or ''
                    parts = en.split('/')
                    if len(parts) >= 3:
                        try:
                            n = int(parts[2])
                            if n > maxn:
                                maxn = n
                        except Exception:
                            continue
                return f"PMC/MAIN/{(maxn+1):03d}"
            except Exception:
                import time
                return f"PMC/MAIN/{int(time.time())%1000:03d}"

        # parse current_km if provided in API request
        try:
            _ck = request.form.get('current_km')
            current_km = int(_ck) if (_ck is not None and str(_ck).strip() != '') else None
        except Exception:
            current_km = None

        data = {
            'entry_no': request.form.get('entry_no') or get_next_entry_no_api(),
            'date_time': request.form.get('date_time'),
            'vehicle_id': vehicle_id,
            'current_km': current_km,
            'registration_no': request.form.get('registration_no'),
            'driver_incharge': request.form.get('driver_incharge'),
            'drivers_voice': request.form.get('drivers_voice'),
            'technician_alloted': request.form.get('technician_alloted'),
            'technician_observation': request.form.get('technician_observation'),
            'possible_ways': request.form.get('possible_ways'),
            'parts_required': request.form.get('parts_required'),
            'processed_by': session.get('user_id') or session.get('admin_id'),
            'approved': False,
            'created_by': session.get('user_id') or session.get('admin_id')
        }

        saved = save_maintenance_entry(data)
        if saved:
            # Try to fetch saved row id/entry_no if save helper returns row or id
            entry_id = None
            entry_no = data.get('entry_no')
            try:
                res = supabase.table('maintenance_entry').select('*').eq('entry_no', entry_no).limit(1).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    entry_id = row.get('id')
            except Exception:
                app.logger.exception('Failed to fetch created maintenance entry by entry_no')

            response = {'success': True, 'message': 'Maintenance job card created.', 'entry_id': entry_id, 'entry_no': entry_no}
            return jsonify(response), 201
        else:
            app.logger.error('save_maintenance_entry returned falsy for data: %s', data)
            return jsonify({'success': False, 'message': 'save_maintenance_entry returned falsy (None).', 'debug_data': {'entry_no': data.get('entry_no'), 'date_time': data.get('date_time')}}), 500
    except Exception as e:
        app.logger.exception('Exception in api_create_maintenance')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/maintenance-history')
@login_required
@module_required('Maintenance')
def maintenance_history():
    try:
        res = supabase.table('maintenance_entry').select('*').order('created_at', desc=True).execute()
        entries = res.data if res.data else []
    except Exception as e:
        flash(f'Error loading maintenance history: {str(e)}', 'danger')
        entries = []
    # load parts for the corrected modal dropdown
    try:
        parts_res = supabase.table('parts').select('part_id, part_name').eq('status', 'active').order('part_name').execute()
        parts = parts_res.data if parts_res.data else []
    except Exception:
        parts = []

    # Enrich entries with total utilized quantity from material_utilization records
    try:
        util_res = supabase.table('material_utilization').select('entry_no, description, quantity').execute()
        util_rows = util_res.data if util_res.data else []
        # map maintenance_id -> total quantity
        util_map = {}
        import re
        for u in util_rows:
            qty = 0
            try:
                qty = float(u.get('quantity') or 0)
            except Exception:
                qty = 0
            desc = (u.get('description') or '')
            entry_no = (u.get('entry_no') or '')
            # try to extract maintenance id from description like 'From maintenance {id}'
            m = re.search(r'From maintenance\s*(\d+)', desc)
            mid = None
            if m:
                mid = int(m.group(1))
            else:
                # try to parse from entry_no like MU/{maintenance_id}/12345
                m2 = re.search(r'MU/(\d+)/', entry_no)
                if m2:
                    try:
                        mid = int(m2.group(1))
                    except Exception:
                        mid = None
            if mid is not None:
                util_map[mid] = util_map.get(mid, 0) + qty

        # attach utilized_qty to entries if present
        for e in entries:
            try:
                eid = int(e.get('id')) if e.get('id') is not None else None
            except Exception:
                eid = None
            e['utilized_qty'] = util_map.get(eid, None)
    except Exception:
        # If enrichment fails, leave entries as-is
        pass

    return render_template('maintenance_history.html', entries=entries, parts=parts)


@app.route('/api/maintenance/low_ratings')
@login_required
def api_low_ratings():
    """Return maintenance entries with rating 1 or 2 (used by Driver Rating modal)."""
    try:
        res = supabase.table('maintenance_entry').select('*').order('created_at', desc=True).execute()
        rows = res.data if res.data else []

        # Enrich with utilized_qty from material_utilization (same approach as maintenance_history)
        try:
            util_res = supabase.table('material_utilization').select('entry_no, description, quantity').execute()
            util_rows = util_res.data if util_res.data else []
            util_map = {}
            import re
            for u in util_rows:
                qty = 0
                try:
                    qty = float(u.get('quantity') or 0)
                except Exception:
                    qty = 0
                desc = (u.get('description') or '')
                entry_no = (u.get('entry_no') or '')
                m = re.search(r'From maintenance\s*(\d+)', desc)
                mid = None
                if m:
                    try:
                        mid = int(m.group(1))
                    except Exception:
                        mid = None
                else:
                    m2 = re.search(r'MU/(\d+)/', entry_no)
                    if m2:
                        try:
                            mid = int(m2.group(1))
                        except Exception:
                            mid = None
                if mid is not None:
                    util_map[mid] = util_map.get(mid, 0) + qty
        except Exception:
            util_map = {}

        low = []
        for r in rows:
            try:
                rv = int(r.get('rating')) if (r.get('rating') is not None and str(r.get('rating')).strip() != '') else None
            except Exception:
                rv = None
            if rv in (1,2):
                # attach utilized_qty if available
                try:
                    eid = int(r.get('id')) if r.get('id') is not None else None
                except Exception:
                    eid = None
                if eid is not None:
                    r['utilized_qty'] = util_map.get(eid, None)
                else:
                    r['utilized_qty'] = None
                low.append(r)
        return jsonify({'success': True, 'rows': low}), 200
    except Exception as e:
        app.logger.exception('Failed to fetch low ratings')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/maintenance/<int:entry_id>/set_pending', methods=['POST'])
@login_required
def maintenance_set_pending(entry_id):
    """Set a job card to pending with an estimated date."""
    try:
        est_date = request.form.get('estimated_date')
        processed_by_form = request.form.get('processed_by')
        day_end_description = request.form.get('day_end_description')
        # Accept processed_by as a free-text name from the modal. If a numeric id is sent,
        # keep it as-is; otherwise store the entered string so the UI can display it.
        data = {'status': 'pending', 'estimated_date': est_date}
        if processed_by_form:
            data['processed_by'] = processed_by_form
        if day_end_description:
            data['day_end_description'] = day_end_description
        updated = update_maintenance_entry(entry_id, data)
        if updated:
            flash('Job card moved to Pending.', 'success')
        else:
            flash('Failed to move job card to Pending.', 'danger')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    # After setting to Pending, return to the maintenance entry page
    return redirect(url_for('maintenance_view', entry_id=entry_id))


@app.route('/maintenance/<int:entry_id>/mark_corrected', methods=['POST'])
@login_required
def maintenance_mark_corrected(entry_id):
    """Mark a pending job card as corrected/approved."""
    try:
        # accept optional parts/feedback and processed_by from modal/form
        # Support multiple parts submitted as arrays: part_id[] and part_qty[]
        part_ids = request.form.getlist('part_id[]') or request.form.getlist('part_id') or []
        part_qtys = request.form.getlist('part_qty[]') or request.form.getlist('part_qty') or []
        # If single values were sent (legacy forms), ensure we still handle them
        if not part_ids:
            single_part = request.form.get('part_id')
            if single_part:
                part_ids = [single_part]
        if not part_qtys:
            single_qty = request.form.get('part_qty')
            if single_qty:
                part_qtys = [single_qty]
        driver_feedback = request.form.get('driver_feedback')
        processed_by_form = request.form.get('processed_by')

        data = {'status': 'corrected', 'approved': True}
        # debug log incoming parts for troubleshooting
        try:
            app.logger.debug('mark_corrected received part_ids=%s part_qtys=%s processed_by=%s', part_ids, part_qtys, processed_by_form)
        except Exception:
            pass
        if driver_feedback:
            # store driver feedback in drivers_voice field for now
            data['drivers_voice'] = (driver_feedback or '')
        # If user provided a processed_by value in the form, store it
        if processed_by_form:
            data['processed_by'] = processed_by_form

        updated = update_maintenance_entry(entry_id, data)
        if updated:
            # If parts were supplied (possibly multiple), record utilization and reduce stock for each
            try:
                if part_ids:
                    app.logger.debug('Mark corrected multiple parts: part_ids=%s part_qtys=%s entry_id=%s', part_ids, part_qtys, entry_id)
                    # try to enrich utilization record with vehicle details once
                    vehicle_id_val = ''
                    vehicle_reg_val = None
                    try:
                        mres = supabase.table('maintenance_entry').select('*').eq('id', entry_id).limit(1).execute()
                        if mres.data and len(mres.data) > 0:
                            mrow = mres.data[0]
                            vehicle_id_val = mrow.get('vehicle_id') or (mrow.get('registration_no') or '')
                            vehicle_reg_val = mrow.get('registration_no')
                    except Exception:
                        vehicle_id_val = ''

                    parts_summary_items = []
                    parts_items = []
                    # iterate through provided arrays; handle length mismatches gracefully
                    max_len = max(len(part_ids), len(part_qtys)) if (part_ids or part_qtys) else 0
                    for i in range(max_len):
                        try:
                            pid = part_ids[i] if i < len(part_ids) else None
                            pqty_raw = part_qtys[i] if i < len(part_qtys) else None
                            if not pid:
                                continue
                            try:
                                pqty = float(pqty_raw) if (pqty_raw is not None and str(pqty_raw).strip() != '') else 0
                            except Exception:
                                pqty = 0
                            if pqty <= 0:
                                # skip zero/invalid quantities
                                continue

                            # try to get part name from purchases or parts table
                            part_name_val = pid
                            try:
                                p_res = supabase.table('purchases').select('part_name').eq('part_number', pid).limit(1).execute()
                                if p_res.data and len(p_res.data) > 0:
                                    part_name_val = p_res.data[0].get('part_name') or pid
                                else:
                                    pp = supabase.table('parts').select('part_name').eq('part_id', pid).limit(1).execute()
                                    if pp.data and len(pp.data) > 0:
                                        part_name_val = pp.data[0].get('part_name') or pid
                            except Exception:
                                part_name_val = pid

                            util = {
                                'date_time': datetime.now().isoformat(),
                                'entry_no': f'MU/{entry_id}/{int(time.time())}',
                                'vehicle_id': vehicle_id_val or '',
                                'vehicle_registration_no': vehicle_reg_val,
                                'part_no': pid,
                                'part_name': part_name_val or pid,
                                'quantity': float(pqty),
                                'description': f'From maintenance {entry_id}',
                                'driver_id': None,
                                'mech_id': None,
                                'processed_by_id': None
                            }
                            # try to set processed_by_id from numeric form value or session id
                            try:
                                if processed_by_form:
                                    if str(processed_by_form).strip().isdigit():
                                        util['processed_by_id'] = int(str(processed_by_form).strip())
                                    else:
                                        util['processed_by_id'] = None
                                else:
                                    sid = session.get('user_id') or session.get('admin_id')
                                    if sid is not None:
                                        try:
                                            util['processed_by_id'] = int(sid)
                                        except Exception:
                                            util['processed_by_id'] = None
                            except Exception:
                                util['processed_by_id'] = None

                            saved = save_material_utilization(util)
                            # support new return shape from save_material_utilization
                            try:
                                saved_row = saved.get('row') if isinstance(saved, dict) else saved
                            except Exception:
                                saved_row = saved
                            if not saved_row:
                                app.logger.warning('save_material_utilization returned falsy for util: %s', util)

                            # Attempt to consume stock even if saving utilization failed
                            try:
                                consume_res = consume_part_from_purchases(pid, float(pqty))
                                app.logger.debug('consume_part_from_purchases result for %s: %s', pid, consume_res)
                                if not consume_res:
                                    app.logger.warning('No purchases were consumed for part %s qty %s', pid, pqty)
                            except Exception as exc2:
                                app.logger.exception('Error during consume_part_from_purchases for %s: %s', pid, exc2)

                            parts_summary_items.append(f"{pid} x{int(pqty) if float(pqty).is_integer() else pqty}")
                            parts_items.append({
                                'part_no': pid,
                                'part_name': part_name_val,
                                'quantity': float(pqty)
                            })
                        except Exception as exc:
                            app.logger.exception('Failed processing part at index %s: %s', i, exc)

                    # update maintenance record with a summary of issued parts and processed_by once
                    if parts_summary_items:
                        summary = 'Issued: ' + '; '.join(parts_summary_items)
                        upd = {'parts_required': summary, 'items_utilized': True, 'utilized_items': parts_items}
                        if processed_by_form:
                            upd['processed_by'] = processed_by_form
                        update_maintenance_entry(entry_id, upd)
                    else:
                        # No parts used: if a no_items_description was provided in the form, save it
                        no_items_desc = request.form.get('no_items_description')
                        if no_items_desc:
                            update_maintenance_entry(entry_id, {'no_items_description': no_items_desc, 'items_utilized': False})
            except Exception as exc:
                app.logger.exception('Failed to record utilization or consume stock for multiple parts: %s', exc)

            flash('Job card marked Corrected.', 'success')
        else:
            flash('Failed to mark job card Corrected.', 'danger')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('maintenance_history'))


@app.route('/maintenance/<int:entry_id>')
@login_required
def maintenance_view(entry_id):
    """View a single maintenance job card details."""
    try:
        res = supabase.table('maintenance_entry').select('*').eq('id', entry_id).limit(1).execute()
        entry = res.data[0] if res.data and len(res.data) > 0 else None
    except Exception as e:
        flash(f'Error loading job card: {str(e)}', 'danger')
        entry = None
    # Enrich single entry with utilized_qty (same logic as maintenance_history)
    try:
        if entry:
            util_res = supabase.table('material_utilization').select('entry_no, description, quantity').execute()
            util_rows = util_res.data if util_res.data else []
            util_map = {}
            import re
            for u in util_rows:
                qty = 0
                try:
                    qty = float(u.get('quantity') or 0)
                except Exception:
                    qty = 0
                desc = (u.get('description') or '')
                entry_no = (u.get('entry_no') or '')
                m = re.search(r'From maintenance\s*(\d+)', desc)
                mid = None
                if m:
                    try:
                        mid = int(m.group(1))
                    except Exception:
                        mid = None
                else:
                    m2 = re.search(r'MU/(\d+)/', entry_no)
                    if m2:
                        try:
                            mid = int(m2.group(1))
                        except Exception:
                            mid = None
                if mid is not None:
                    util_map[mid] = util_map.get(mid, 0) + qty
            try:
                eid = int(entry.get('id')) if entry.get('id') is not None else None
            except Exception:
                eid = None
            entry['utilized_qty'] = util_map.get(eid, None)
    except Exception:
        pass
    return render_template('maintenance_view.html', entry=entry)


@app.route('/admin/internal_audits')
@admin_required
def admin_internal_audits():
    """Admin view: show recent internal audits from DB and any locally saved fallback entries."""
    audits_db = []
    audits_fallback = []
    # Fetch from Supabase internal_audits table if available
    try:
        res = supabase.table('internal_audits').select('*').order('created_at', desc=True).limit(200).execute()
        audits_db = res.data if res.data else []
    except Exception as e:
        app.logger.exception('Failed to fetch internal_audits from DB')
        audits_db = []

    # Enrich DB rows with employee name/designation when possible so admin preview shows them
    try:
        # fetch employees mapping once
        emp_map = {}
        try:
            emp_res = supabase.table('employees').select('employee_id, name, full_name, designation').execute()
            emp_rows = emp_res.data if getattr(emp_res, 'data', None) else []
            for er in emp_rows:
                key = er.get('employee_id') or er.get('id')
                if key:
                    emp_map[str(key)] = {
                        'name': er.get('name') or er.get('full_name') or '',
                        'designation': er.get('designation') or ''
                    }
        except Exception:
            emp_map = {}

        # attach name/designation to each audit record when missing
        for a in audits_db:
            try:
                # auditor_1
                a.setdefault('auditor_1_name', a.get('auditor_1_name') or '')
                a.setdefault('auditor_1_designation', a.get('auditor_1_designation') or '')
                # auditor_2
                a.setdefault('auditor_2_name', a.get('auditor_2_name') or '')
                a.setdefault('auditor_2_designation', a.get('auditor_2_designation') or '')
                # auditee
                a.setdefault('auditee_name', a.get('auditee_name') or '')
                a.setdefault('auditee_designation', a.get('auditee_designation') or '')

                # lookup from emp_map by id if values still empty
                if (not a.get('auditor_1_name')) and a.get('auditor_1') and str(a.get('auditor_1')) in emp_map:
                    a['auditor_1_name'] = emp_map[str(a.get('auditor_1'))]['name']
                    a['auditor_1_designation'] = emp_map[str(a.get('auditor_1'))]['designation']
                if (not a.get('auditor_2_name')) and a.get('auditor_2') and str(a.get('auditor_2')) in emp_map:
                    a['auditor_2_name'] = emp_map[str(a.get('auditor_2'))]['name']
                    a['auditor_2_designation'] = emp_map[str(a.get('auditor_2'))]['designation']
                if (not a.get('auditee_name')) and a.get('auditee') and str(a.get('auditee')) in emp_map:
                    a['auditee_name'] = emp_map[str(a.get('auditee'))]['name']
                    a['auditee_designation'] = emp_map[str(a.get('auditee'))]['designation']
            except Exception:
                continue
    except Exception:
        # non-fatal: if enrichment fails, continue without names
        app.logger.exception('Failed to enrich audits with employee names')

    # Load fallback file if present (last 200 lines)
    fallback_path = os.path.join(os.getcwd(), 'internal_audits_fallback.jsonl')
    try:
        if os.path.exists(fallback_path):
            with open(fallback_path, 'r', encoding='utf-8') as fh:
                import json
                lines = fh.read().strip().splitlines()
                # keep most recent 200
                for ln in lines[-200:][::-1]:
                    try:
                        j = json.loads(ln)
                        # ensure ts and payload keys exist
                        audits_fallback.append({'ts': j.get('ts'), 'error': j.get('error'), 'payload': j.get('payload')})
                    except Exception:
                        continue
            # Merge fallback payloads into audits_db at the front so recently-saved-local entries show in admin
            try:
                fallback_payloads = []
                for f in audits_fallback:
                    p = f.get('payload') or {}
                    if isinstance(p, dict):
                        # annotate that this row came from fallback
                        p['_from_fallback'] = True
                        p['_fallback_ts'] = f.get('ts')
                        p['_fallback_error'] = f.get('error')
                        fallback_payloads.append(p)
                if fallback_payloads:
                    # prepend fallback payloads so newest appear first
                    audits_db = fallback_payloads + (audits_db or [])
                    # avoid double-listing in the fallback table area
                    audits_fallback = []
            except Exception:
                app.logger.exception('Failed to merge fallback payloads')
    except Exception:
        app.logger.exception('Failed to read fallback internal audits file')

    return render_template('admin_internal_audits.html', audits_db=audits_db, audits_fallback=audits_fallback)


@app.route('/maintenance/<int:entry_id>/edit', methods=['GET', 'POST'])
@login_required
@module_required('Maintenance')
def maintenance_edit(entry_id):
    """Edit an existing maintenance job card. GET renders the form prefilled, POST updates the row."""
    try:
        # fetch existing entry
        res = supabase.table('maintenance_entry').select('*').eq('id', entry_id).limit(1).execute()
        entry = res.data[0] if res.data and len(res.data) > 0 else None
    except Exception as e:
        flash(f'Error loading job card for edit: {e}', 'danger')
        return redirect(url_for('maintenance_history'))

    if request.method == 'POST':
        try:
            # accept vehicle_id as-is (vehicle ids can be alphanumeric)
            vehicle_id = request.form.get('vehicle_id') or None

            try:
                _ck = request.form.get('current_km')
                current_km = int(_ck) if (_ck is not None and str(_ck).strip() != '') else None
            except Exception:
                current_km = None

            data = {
                'date_time': request.form.get('date_time'),
                'vehicle_id': vehicle_id,
                'current_km': current_km,
                'registration_no': request.form.get('registration_no'),
                'driver_incharge': request.form.get('driver_incharge'),
                'drivers_voice': request.form.get('drivers_voice'),
                'technician_alloted': request.form.get('technician_alloted'),
                'technician_observation': request.form.get('technician_observation'),
                'possible_ways': request.form.get('possible_ways'),
                'parts_required': request.form.get('parts_required')
            }
            updated = update_maintenance_entry(entry_id, data)
            if updated:
                flash('Job card updated successfully.', 'success')
                return redirect(url_for('maintenance_view', entry_id=entry_id))
            else:
                flash('Failed to update job card.', 'danger')
        except Exception as e:
            flash(f'Error updating job card: {e}', 'danger')

    # GET - render the same form but pass the entry so template can prefill
    try:
        vehicles_res = supabase.table('vehicles').select('vehicle_id, registration_no').order('vehicle_id').execute()
        vehicles = vehicles_res.data if vehicles_res.data else []
    except Exception:
        vehicles = []

    return render_template('maintenance_image.html', vehicles=vehicles, entry=entry)


@app.route('/maintenance/<int:entry_id>/rate', methods=['POST'])
@login_required
def maintenance_rate(entry_id):
    """Save a numeric rating (1-5) for a maintenance entry."""
    try:
        rating_raw = request.form.get('rating')
        rating = None
        if rating_raw is not None and rating_raw != '':
            try:
                rating = int(rating_raw)
                if rating < 1 or rating > 5:
                    rating = None
            except Exception:
                rating = None
        # store rating (allow null to clear). Do NOT change status here
        update_data = {'rating': rating}
        # include optional rating description when provided
        try:
            rating_desc = (request.form.get('rating_description') or '').strip()
            if rating_desc != '':
                update_data['rating_description'] = rating_desc
        except Exception:
            pass
        updated = update_maintenance_entry(entry_id, update_data)
        if updated:
            entry = None
            try:
                res = supabase.table('maintenance_entry').select('*').eq('id', entry_id).limit(1).execute()
                entry = res.data[0] if res.data and len(res.data) > 0 else None
            except Exception:
                entry = None
            return jsonify({'success': True, 'rating': rating, 'entry': entry}), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to update'}), 500
    except Exception as e:
        app.logger.exception('Error saving rating')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/debug/logs')
@login_required
def debug_logs():
    """Temporary route: return recent in-memory app logs as JSON."""
    try:
        # Return latest logs (most recent last)
        return jsonify(list(LOG_BUFFER)), 200
    except Exception as e:
        app.logger.exception('Failed to return debug logs')
        return jsonify({'error': str(e)}), 500


@app.route('/debug/part/<part_id>')
@login_required
def debug_part(part_id):
    """Temporary debug endpoint: return purchases, utilization, scrap and issues for a part_id."""
    try:
        # All purchases (include statuses) and a filtered view
        pur_res = supabase.table('purchases').select('*').order('created_at', desc=False).execute()
        purchases = pur_res.data if pur_res.data else []

        matched = []
        for p in purchases:
            pn = (p.get('part_number') or p.get('part_no') or '')
            pn_norm = pn.strip().lower() if isinstance(pn, str) else str(pn).lower()
            if pn_norm == str(part_id).strip().lower():
                matched.append({
                    'id': p.get('id'),
                    'part_number': p.get('part_number'),
                    'part_no': p.get('part_no'),
                    'quantity': p.get('quantity'),
                    'status': p.get('status'),
                    'net_payable': p.get('net_payable')
                })

        util_res = supabase.table('material_utilization').select('*').eq('part_no', part_id).execute()
        scrap_res = supabase.table('scrap').select('*').eq('part_no', part_id).execute()
        issues_res = supabase.table('stock_issue_register').select('*').eq('part_no', part_id).execute()

        # include recent application logs to help diagnose whether consumption ran
        recent_logs = list(LOG_BUFFER)
        return jsonify({
            'part_id': part_id,
            'matched_purchases': matched,
            'all_purchases_count': len(purchases),
            'utilization': util_res.data if util_res.data else [],
            'scrap': scrap_res.data if scrap_res.data else [],
            'issues': issues_res.data if issues_res.data else [],
            'recent_logs': recent_logs
        }), 200
    except Exception as e:
        app.logger.exception('Error in debug_part')
        return jsonify({'error': str(e)}), 500


@app.route('/api/part_availability/<part_id>')
@login_required
def api_part_availability(part_id):
    """Return available quantity for a given part_id.
    Calculation: SUM(purchases.quantity where part_no=part_id and status='active')
                 - SUM(stock_issue_register.quantity_issued where part_no=part_id)
                 - SUM(material_utilization.quantity where part_no=part_id)
    """
    try:
        # Helper to safely extract a numeric quantity from a record using common field names
        def _extract_qty(record, candidates):
            for k in candidates:
                if k in record:
                    try:
                        return float(record.get(k) or 0)
                    except Exception:
                        try:
                            return float(str(record.get(k)).strip() or 0)
                        except Exception:
                            return 0
            return 0

        # Compute available quantity by summing the current `quantity` field
        # from `purchases` for rows that match the given part id. The
        # `purchases.quantity` field is treated as the canonical remaining
        # stock (FIFO consumption updates it), so we rely on it rather than
        # attempting to subtract separate issue/utilization records here.
        total_purchased = 0
        pur_res = supabase.table('purchases').select('*').execute()
        if pur_res.data:
            for r in pur_res.data:
                pn = (r.get('part_number') or r.get('part_no') or '')
                pn = pn.strip() if isinstance(pn, str) else str(pn)
                if not pn:
                    continue
                try:
                    if pn.lower() == str(part_id).lower():
                        total_purchased += _extract_qty(r, ['quantity', 'qty', 'Quantity'])
                except Exception:
                    if pn == part_id:
                        total_purchased += _extract_qty(r, ['quantity', 'qty', 'Quantity'])

        # We no longer subtract issue/utilization records here because those
        # operations should already have updated `purchases.quantity`. Return
        # the summed remaining quantity as the available amount.
        available = total_purchased
        if available < 0:
            available = 0
        return jsonify({'part_id': part_id, 'available': available}), 200
    except Exception as e:
        app.logger.exception('Error computing part availability for %s', part_id)
        # Return a safe JSON response so clients (AJAX) can still show availability as 0
        return jsonify({'part_id': part_id, 'available': 0, 'error': str(e)}), 200

# Part ID Generator Route
@app.route('/part-generator', methods=['GET', 'POST'])
@login_required
@module_required('Part ID')
def part_generator():
    """Part ID Generator for creating and managing parts"""
    if request.method == 'POST':
        try:
            data = {
                'part_id': request.form.get('part_id'),
                'part_name': request.form.get('part_name'),
                'category': request.form.get('category'),
                'unit': request.form.get('unit'),
                'description': request.form.get('description'),
                'created_by': session.get('user_id') or session.get('user'),
                'status': 'active'
            }
            
            result = supabase.table('parts').insert(data).execute()
            
            if result.data:
                flash('Part ID created successfully!', 'success')
            else:
                flash('Error creating Part ID.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('part_generator'))
    
    # GET request - show form
    try:
        # Get all parts
        all_parts = supabase.table('parts').select('*').order('created_at', desc=True).execute()
        parts = all_parts.data if all_parts.data else []
        
        return render_template('part_generator.html', parts=parts)
    except Exception as e:
        flash(f'Error loading parts: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/part-generator/<part_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_part(part_id):
    """Edit existing part"""
    try:
        if request.method == 'POST':
            new_part_id = request.form.get('part_id')
            
            # Update part data
            update_data = {
                'part_id': new_part_id,
                'part_name': request.form.get('part_name'),
                'category': request.form.get('category'),
                'unit': request.form.get('unit'),
                'description': request.form.get('description'),
                'status': request.form.get('status', 'active')
            }
            
            result = supabase.table('parts').update(update_data).eq('part_id', part_id).execute()
            
            if result.data:
                flash('Part updated successfully!', 'success')
                return redirect(url_for('part_generator'))
            else:
                flash('Error updating part.', 'danger')
        
        # GET request - load part data
        print(f"[DEBUG] Fetching part with ID: {part_id}")
        response = supabase.table('parts').select('*').eq('part_id', part_id).execute()
        print(f"[DEBUG] Query response: {response.data}")
        
        if response.data and len(response.data) > 0:
            part = response.data[0]
            print(f"[DEBUG] Part found: {part}")
            return render_template('edit_part.html', part=part)
        else:
            print(f"[DEBUG] No part found for ID: {part_id}")
            flash('Part not found', 'danger')
            return redirect(url_for('part_generator'))
            
    except Exception as e:
        print(f"[ERROR] Error editing part: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('part_generator'))

# Dashboard Menu Routes
@app.route('/purchase', methods=['GET', 'POST'])
@login_required
@module_required('Purchase')
def purchase():
    if request.method == 'POST':
        try:
            data = {
                'date': request.form.get('date'),
                'time': request.form.get('time'),
                'entry_no': request.form.get('entry_no'),
                'invoice_no': request.form.get('invoice_no'),
                'invoice_date': request.form.get('invoice_date'),
                'vendor': request.form.get('vendor'),
                'type_of_purchase': request.form.get('type_of_purchase'),
                'part_number': request.form.get('part_number'),
                'part_name': request.form.get('part_name'),
                'quantity': request.form.get('quantity'),
                'batch_number': request.form.get('batch_number'),
                'rate': request.form.get('rate'),
                'discount_percent': request.form.get('discount_percent'),
                'discount_amount': request.form.get('discount_amount'),
                'taxable_amount': request.form.get('taxable_amount'),
                'sgst_percent': request.form.get('sgst_percent'),
                'sgst_amount': request.form.get('sgst_amount'),
                'cgst_percent': request.form.get('cgst_percent'),
                'cgst_amount': request.form.get('cgst_amount'),
                'igst_percent': request.form.get('igst_percent'),
                'igst_amount': request.form.get('igst_amount'),
                'total_payment': request.form.get('total_payment'),
                'dn': request.form.get('dn'),
                'less_tds': request.form.get('less_tds'),
                'net_payable': request.form.get('net_payable'),
                'reference_number': request.form.get('reference_number'),
                'comments': request.form.get('comments'),
                'user_id': session.get('user_id')
            }
            result = save_purchase(data)
            if result:
                flash('Purchase record saved successfully!', 'success')
                return redirect(url_for('purchase', success='true'))
            else:
                flash('Error: Failed to save purchase record. Please check the console for details.', 'danger')
        except Exception as e:
            flash(f'Purchase Save Error: {str(e)}', 'danger')
            print(f"Purchase error details: {str(e)}")
            import traceback
            traceback.print_exc()
        return redirect(url_for('purchase'))
    
    # Get next entry number for auto-fill
    next_entry_no = get_next_purchase_entry_no()
    
    # Get all active vendors for dropdown
    try:
        # Try to fetch including the legacy `type_of_purchase` column (may not exist if schema migrated)
        vendors_result = supabase.table('vendors').select('vendor_id, organization_name, type_of_purchase').eq('status', 'active').order('organization_name').execute()
        vendors = vendors_result.data if vendors_result.data else []
    except Exception as e:
        # Fallback: fetch without the column to avoid PostgREST schema errors
        print(f"Error fetching vendors with type_of_purchase: {e} -- falling back to minimal select")
        try:
            vendors_result = supabase.table('vendors').select('vendor_id, organization_name').eq('status', 'active').order('organization_name').execute()
            vendors = vendors_result.data if vendors_result.data else []
        except Exception as e2:
            print(f"Error fetching vendors: {e2}")
            vendors = []
    
    # Get all active parts for dropdown
    try:
        parts_result = supabase.table('parts').select('part_id, part_name').eq('status', 'active').order('part_name').execute()
        parts = parts_result.data if parts_result.data else []
    except Exception as e:
        print(f"Error fetching parts: {e}")
        parts = []
    
    return render_template('purchase.html', entry_no=next_entry_no, vendors=vendors, parts=parts)

@app.route('/utilization', methods=['GET', 'POST'])
@login_required
@module_required('Utilization')
def utilization():
    """Material Utilization form for recording material usage"""
    if request.method == 'POST':
        try:
            # Collect form data
            data = {
                'entry_no': request.form.get('entry_no'),
                'date_time': request.form.get('date_time'),
                'vehicle_id': request.form.get('vehicle_id'),
                'vehicle_registration_no': request.form.get('vehicle_registration_no'),
                'part_no': request.form.get('part_no'),
                'part_name': request.form.get('part_name'),
                'quantity': request.form.get('quantity'),
                'description': request.form.get('description'),
                'driver_id': request.form.get('driver_id'),
                'mech_id': request.form.get('mech_id'),
                'processed_by_id': request.form.get('processed_by_id'),
                'approved': request.form.get('approved'),
                'reference_number': request.form.get('reference_number'),
                'comments': request.form.get('comments')
            }
            
            # Save to material_utilization table
            result = supabase.table('material_utilization').insert(data).execute()

            if result.data:
                # After recording utilization, consume stock from purchases using FIFO
                try:
                    try:
                        qty_to_consume = float(data.get('quantity') or 0)
                    except Exception:
                        qty_to_consume = 0
                    if qty_to_consume > 0 and data.get('part_no'):
                        consume_res = consume_part_from_purchases(data.get('part_no'), qty_to_consume)
                        app.logger.debug('consume_part_from_purchases result for utilization: %s', consume_res)
                except Exception as exc:
                    app.logger.exception('Error consuming stock after utilization insert: %s', exc)

                flash('Material utilization record submitted successfully!', 'success')
                return redirect(url_for('utilization'))
            else:
                flash('Error submitting utilization record.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    # GET request - show form
    try:
        # Generate entry number manually from database
        import re
        existing = supabase.table('material_utilization').select('entry_no').order('created_at', desc=True).limit(1).execute()
        if existing.data and existing.data[0].get('entry_no'):
            last_entry = existing.data[0]['entry_no']
            # Extract the sequential number at the end (e.g., PMCTECH/LOGI/UTI/001 -> 001)
            match = re.search(r'(\d+)$', last_entry)
            if match:
                next_num = int(match.group(1)) + 1
                entry_no = f'PMCTECH/LOGI/UTI/{str(next_num).zfill(3)}'
            else:
                entry_no = 'PMCTECH/LOGI/UTI/001'
        else:
            entry_no = 'PMCTECH/LOGI/UTI/001'
        
        # Get all vehicles for dropdown
        vehicles = supabase.table('vehicles').select('vehicle_id, registration_no').order('vehicle_id').execute()
        
        # --- Compute available quantities the same way stock_inventory does ---
        # purchases.quantity is ALREADY decremented by consume_part_from_purchases on every
        # utilization save, so we must NOT subtract utilization/scrap records a second time.
        # Instead we reconstruct original_qty = current_qty + utilized + scrapped, then
        # available = original_qty - utilized - scrapped  ==  current_qty  (same as stock_inventory).

        # Get ALL purchase rows so we can use their current (already-deducted) quantity
        purchases = supabase.table('purchases').select('part_number, part_name, quantity, status').execute()

        # Get all utilized quantities from material_utilization
        utilized = supabase.table('material_utilization').select('part_no, quantity').execute()

        # Get all scrapped quantities from scrap
        scrapped = supabase.table('scrap').select('part_no, quantity').execute()

        # ---- Build utilization totals keyed by lowercase part_no ----
        utilized_by_part = {}
        if utilized.data:
            for item in utilized.data:
                raw_part = item.get('part_no') or item.get('part_number') or ''
                if not raw_part:
                    continue
                pkey = str(raw_part).strip().lower()
                try:
                    utilized_by_part[pkey] = utilized_by_part.get(pkey, 0) + float(item.get('quantity', 0) or 0)
                except Exception:
                    pass

        # ---- Build scrap totals keyed by lowercase part_no ----
        scrapped_by_part = {}
        if scrapped.data:
            for item in scrapped.data:
                raw_part = item.get('part_no') or item.get('part_number') or ''
                if not raw_part:
                    continue
                pkey = str(raw_part).strip().lower()
                try:
                    scrapped_by_part[pkey] = scrapped_by_part.get(pkey, 0) + float(item.get('quantity', 0) or 0)
                except Exception:
                    pass

        # ---- Aggregate purchases by part (current remaining qty) ----
        parts_dict = {}
        if purchases.data:
            for item in purchases.data:
                raw_part = item.get('part_number') or item.get('part_no') or item.get('part') or ''
                if not raw_part:
                    continue
                part_no = str(raw_part).strip()
                pkey = part_no.lower()

                if pkey not in parts_dict:
                    parts_dict[pkey] = {
                        'part_no': part_no,
                        'part_name': item.get('part_name') or '',
                        'current_qty': 0,   # sum of purchases.quantity (already deducted)
                    }

                status_val = (item.get('status') or '').lower()
                # Skip rows fully consumed/removed — their quantity is already 0
                if status_val in ('issued', 'consumed', 'removed', 'scrapped', 'deleted'):
                    continue

                try:
                    parts_dict[pkey]['current_qty'] += float(item.get('quantity', 0) or 0)
                except Exception:
                    pass

        # ---- Reconstruct available the same way stock_inventory does ----
        # available = current_qty  (== original_qty - utilized - scrapped, simplified)
        parts_list = []
        for pkey, part in parts_dict.items():
            current_qty = part['current_qty']
            utilized_qty = utilized_by_part.get(pkey, 0)
            scrapped_qty = scrapped_by_part.get(pkey, 0)

            # Reconstruct original to derive correct available (matches stock_inventory logic)
            original_qty = current_qty + utilized_qty + scrapped_qty
            available = original_qty - utilized_qty - scrapped_qty  # == current_qty
            display_avail = round(available, 2) if available > 0 else 0.0

            # Only show parts that have some stock history
            if original_qty > 0 or current_qty > 0:
                parts_list.append({
                    'part_no': part.get('part_no') or '',
                    'part_name': part.get('part_name') or '',
                    'available_quantity': display_avail
                })
        
        # Sort by part_no (handle None values)
        parts_list.sort(key=lambda x: x['part_no'] or '')
        
        return render_template('material_utilization.html', 
                             entry_no=entry_no,
                             vehicles=vehicles.data if vehicles.data else [],
                             parts=parts_list)
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/scrap', methods=['GET', 'POST'])
@login_required
@module_required('Scrap')
def scrap():
    """Scrap form for recording scrapped/damaged parts"""
    if request.method == 'POST':
        try:
            # Collect form data
            data = {
                'entry_no': request.form.get('entry_no'),
                'date_time': request.form.get('date_time'),
                'vehicle_id': request.form.get('vehicle_id'),
                'vehicle_registration_no': request.form.get('vehicle_registration_no'),
                'part_no': request.form.get('part_no'),
                'part_name': request.form.get('part_name'),
                'quantity': request.form.get('quantity'),
                'type_of_material': request.form.get('type_of_material'),
                'driver_id': request.form.get('driver_id'),
                'mech_id': request.form.get('mech_id'),
                'processed_by_id': request.form.get('processed_by_id'),
                'approved': request.form.get('approved'),
                'reference_number': request.form.get('reference_number'),
                'comments': request.form.get('comments')
            }
            
            # Save to scrap table
            result = supabase.table('scrap').insert(data).execute()
            
            if result.data:
                flash('Scrap record submitted successfully!', 'success')
                return redirect(url_for('scrap'))
            else:
                flash('Error submitting scrap record.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    # GET request - show form
    try:
        # Generate entry number manually from database
        import re
        existing = supabase.table('scrap').select('entry_no').order('created_at', desc=True).limit(1).execute()
        if existing.data and existing.data[0].get('entry_no'):
            last_entry = existing.data[0]['entry_no']
            # Extract the sequential number at the end (e.g., PMCTECH/LOGI/SCRAP/2527/001 -> 001)
            match = re.search(r'(\d+)$', last_entry)
            if match:
                next_num = int(match.group(1)) + 1
                # Replace the last number with incremented value
                entry_no = re.sub(r'\d+$', str(next_num).zfill(3), last_entry)
            else:
                entry_no = 'PMCTECH/LOGI/SCRAP/2528/001'
        else:
            entry_no = 'PMCTECH/LOGI/SCRAP/2528/001'
        
        # Get all vehicles for dropdown
        vehicles = supabase.table('vehicles').select('vehicle_id, registration_no').order('vehicle_id').execute()
        
        # Get active parts from purchases
        purchases = supabase.table('purchases').select('part_number, part_name, quantity').eq('status', 'active').execute()
        
        # Get all utilized quantities from material_utilization
        utilized = supabase.table('material_utilization').select('part_no, quantity').execute()
        
        # Get all scrapped quantities from scrap
        scrapped = supabase.table('scrap').select('part_no, quantity').execute()
        
        # Calculate available quantities
        parts_dict = {}
        
        # Add purchased quantities
        if purchases.data:
            for item in purchases.data:
                part_no = item['part_number']
                if part_no not in parts_dict:
                    parts_dict[part_no] = {
                        'part_no': part_no,
                        'part_name': item['part_name'],
                        'purchased': 0,
                        'utilized': 0,
                        'scrapped': 0
                    }
                parts_dict[part_no]['purchased'] += float(item.get('quantity', 0))
        
        # Subtract utilized quantities
        if utilized.data:
            for item in utilized.data:
                part_no = item['part_no']
                if part_no in parts_dict:
                    parts_dict[part_no]['utilized'] += float(item.get('quantity', 0))
        
        # Subtract scrapped quantities
        if scrapped.data:
            for item in scrapped.data:
                part_no = item['part_no']
                if part_no in parts_dict:
                    parts_dict[part_no]['scrapped'] += float(item.get('quantity', 0))
        
        # Calculate available quantity and filter
        parts_list = []
        for part in parts_dict.values():
            available = part['purchased'] - part['utilized'] - part['scrapped']
            if available > 0:
                parts_list.append({
                    'part_no': part['part_no'],
                    'part_name': part['part_name'],
                    'available_quantity': round(available, 2)
                })
        
        # Sort by part_no
        parts_list.sort(key=lambda x: x['part_no'])
        
        return render_template('scrap.html', 
                             entry_no=entry_no,
                             vehicles=vehicles.data,
                             parts=parts_list)
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/stock-store', methods=['GET', 'POST'])
@login_required
def stock_store():
    """Display form to issue stock items from inventory"""
    if request.method == 'POST':
        try:
            # Get form data
            issue_data = {
                'entry_no': request.form.get('entry_no'),
                'purchase_id': request.form.get('purchase_id'),
                'part_no': request.form.get('part_no'),
                'part_name': request.form.get('part_name'),
                'vehicle_no': request.form.get('vehicle_no'),
                'vehicle_id': request.form.get('vehicle_id'),
                'date': request.form.get('date'),
                'time': request.form.get('time'),
                'kilometer': request.form.get('kilometer'),
                'issuing_person_name': request.form.get('issuing_person_name'),
                'driver_responsible': request.form.get('driver_responsible'),
                'mechanic_responsible': request.form.get('mechanic_responsible'),
                'comments': request.form.get('comments'),
                'status': 'issued'
            }
            
            # Save to stock_issue_register table
            result = supabase.table('stock_issue_register').insert(issue_data).execute()
            
            if result.data:
                # Update purchase item status to 'issued'
                supabase.table('purchases').update({'status': 'issued'}).eq('id', issue_data['purchase_id']).execute()
                flash('Stock issued successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Error issuing stock.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    # GET request - show form
    try:
        # Get next entry number
        entry_no_result = supabase.rpc('get_next_stock_issue_entry_no').execute()
        entry_no = entry_no_result.data if entry_no_result.data else '001'
        
        # Get all purchase items (include issued rows too) - we'll compute available qty per row
        items = supabase.table('purchases').select('*').order('created_at', desc=True).execute()
        
        return render_template('stock_store.html', 
                             entry_no=entry_no,
                             items=items.data)
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/stock-inventory')
@login_required
def stock_inventory():
    """Display all purchase items in inventory with utilization and scrap details"""
    try:
        # Get all purchase items (include active and issued) - we'll compute available qty per row
        items = supabase.table('purchases').select('*').order('created_at', desc=True).execute()
        
        # Get issued items for history
        issued_items = supabase.table('purchases').select('*').eq('status', 'issued').order('updated_at', desc=True).execute()
        
        # Get utilization records
        utilization_records = supabase.table('material_utilization').select('*').order('created_at', desc=True).execute()
        # Normalize field names: some inserts use 'part_number' while others use 'part_no'.
        try:
            if utilization_records.data:
                for r in utilization_records.data:
                    # prefer explicit 'part_no', then 'part_number', then 'part_no ' variants
                    pn = None
                    for k in ('part_no', 'part_number', 'part_no '):
                        if k in r and r.get(k) not in (None, ''):
                            pn = r.get(k)
                            break
                    if pn is None:
                        # try lowercase keys too
                        for k in list(r.keys()):
                            if k.lower().strip() in ('part_no', 'partnumber', 'partno'):
                                pn = r.get(k)
                                break
                    if pn is not None:
                        try:
                            r['part_no'] = str(pn).strip()
                        except Exception:
                            r['part_no'] = pn
                    else:
                        r['part_no'] = ''
        except Exception:
            pass
        
        # Get scrap records
        scrap_records = supabase.table('scrap').select('*').order('created_at', desc=True).execute()
        # Get stock issue register records (issued quantities)
        issue_register_records = supabase.table('stock_issue_register').select('*').order('created_at', desc=True).execute()
        
        # Build dict of utilized quantities by normalized part_no (lowercase trimmed)
        utilized_by_part = {}
        if utilization_records.data:
            for record in utilization_records.data:
                raw_part = record.get('part_no')
                if raw_part is None:
                    continue
                try:
                    part_no_key = str(raw_part).strip().lower()
                except Exception:
                    part_no_key = str(raw_part)
                qty = float(record.get('quantity', 0) or 0)
                utilized_by_part[part_no_key] = utilized_by_part.get(part_no_key, 0) + qty
        
        # Build dict of scrapped quantities by normalized part_no
        scrapped_by_part = {}
        if scrap_records.data:
            for record in scrap_records.data:
                raw_part = record.get('part_no')
                if raw_part is None:
                    continue
                try:
                    part_no_key = str(raw_part).strip().lower()
                except Exception:
                    part_no_key = str(raw_part)
                qty = float(record.get('quantity', 0) or 0)
                scrapped_by_part[part_no_key] = scrapped_by_part.get(part_no_key, 0) + qty
        
        # Calculate statistics for ALL items and filter for display
        available_items = []
        vendors = set()
        purchase_types = set()
        total_value_all_purchases = 0  # Total value of ALL purchases (original purchase values)
        total_current_qty = 0         # Sum of current remaining quantities (purchases.quantity)
        total_available_qty = 0
        total_utilized_qty = 0
        total_scrapped_qty = 0
        total_issued_qty = 0
        instock_value = 0  # Value of items with available quantity > 0
        utilized_value = 0  # Value of utilized quantities
        scrapped_value = 0  # Value of scrapped quantities
        
        # Build cost_per_unit mapping and aggregate purchases by part_no
        cost_per_unit_map = {}
        parts_aggregate = {}  # key = part_key (lowercase), value = dict with aggregated data
        
        # First pass: aggregate all purchases by part to compute totals
        for item in items.data:
            raw_part_no = item.get('part_number') or item.get('part_no') or item.get('part')
            try:
                part_no = str(raw_part_no).strip()
                part_key = part_no.lower()
            except Exception:
                part_no = raw_part_no
                part_key = str(raw_part_no)
            
            purchased_qty = float(item.get('quantity', 0) or 0)
            # some rows use 'original_quantity' to record the received amount before edits
            original_qty = float(item.get('original_quantity', 0) or 0)
            # monetary fields
            item_net_payable = float(item.get('net_payable', 0) or 0)
            # rate may be present as per-unit or total depending on how data was entered
            try:
                rate_val = float(item.get('rate')) if item.get('rate') is not None else None
            except Exception:
                rate_val = None

            # Calculate per-unit cost using sensible fallbacks for service/zero-quantity rows
            if purchased_qty > 0:
                cost_per_unit = item_net_payable / purchased_qty if item_net_payable and purchased_qty else (rate_val or 0)
            elif original_qty > 0:
                cost_per_unit = item_net_payable / original_qty if item_net_payable and original_qty else (rate_val or 0)
            elif rate_val and rate_val > 0:
                # treat `rate` as the unit price for service items
                cost_per_unit = rate_val
            elif item_net_payable > 0:
                # fallback: treat the whole payable as one unit price
                cost_per_unit = item_net_payable
            else:
                cost_per_unit = 0
            
            # Store cost per unit for this part (use average if multiple purchases)
            if part_key in cost_per_unit_map:
                cost_per_unit_map[part_key] = (cost_per_unit_map[part_key] + cost_per_unit) / 2
            else:
                cost_per_unit_map[part_key] = cost_per_unit
            
            # Initialize or update aggregates for this part
            if part_key not in parts_aggregate:
                parts_aggregate[part_key] = {
                    'entry_no': item.get('entry_no', ''),
                    'invoice_no': item.get('invoice_no', ''),
                    'invoice_date': item.get('invoice_date', item.get('date', '')),
                    'date': item.get('date', item.get('invoice_date', '')),
                    'part_number': item.get('part_number') or item.get('part_no'),
                    'part_no': part_no,
                    'part_name': item.get('part_name', ''),
                    'vendor': item.get('vendor', ''),
                    'type_of_purchase': item.get('type_of_purchase', ''),
                    'date_created': item.get('created_at', item.get('date', '')),
                    'current_qty': 0,  # sum of remaining quantities (purchases.quantity after consumption)
                    'total_payable': 0  # sum of net payable
                }
            
            # Accumulate quantities and cost
            parts_aggregate[part_key]['current_qty'] += purchased_qty
            parts_aggregate[part_key]['total_payable'] += item_net_payable
            total_value_all_purchases += item_net_payable
        
        # Second pass: build display rows (one per part) with correct calculations
        for part_key, part_data in parts_aggregate.items():
            utilized_qty = utilized_by_part.get(part_key, 0)
            scrapped_qty = scrapped_by_part.get(part_key, 0)
            
            # Original received = current remaining + what was utilized + what was scrapped
            original_qty = part_data['current_qty'] + utilized_qty + scrapped_qty
            
            # Available = original - utilized - scrapped (or simply = current_qty since consumption already updated it)
            available_qty = original_qty - utilized_qty - scrapped_qty
            
            # Only show items that have availability > 0
            if available_qty > 0:
                cost_per_unit = cost_per_unit_map.get(part_key, 0)
                
                display_row = {
                    'entry_no': part_data['entry_no'],
                    'invoice_no': part_data['invoice_no'],
                    'date': part_data['date'],
                    'invoice_date': part_data['invoice_date'],
                    'part_number': part_data['part_number'],
                    'part_no': part_data['part_no'],
                    'part_name': part_data['part_name'],
                    'vendor': part_data['vendor'],
                    'type_of_purchase': part_data['type_of_purchase'],
                    'date_created': part_data['date_created'],
                    'purchased_quantity': round(original_qty, 2),  # Original received (never changes)
                    'available_quantity': round(available_qty, 2),  # Remaining after utilization/scrap
                    'utilized_quantity': round(utilized_qty, 2),    # Total utilized
                    'scrapped_quantity': round(scrapped_qty, 2),    # Total scrapped
                    'net_payable': round(part_data['total_payable'], 2)
                }
                
                available_items.append(display_row)
                vendors.add(part_data['vendor'])
                purchase_types.add(part_data['type_of_purchase'])
                
                total_available_qty += available_qty
                instock_value += available_qty * cost_per_unit
                total_current_qty += part_data['current_qty']
        
        # Note: `items` already contains purchases of all statuses (including issued),
        # so we do NOT re-add issued purchase rows to totals here to avoid double-counting.

        # Sum issued quantities from stock_issue_register for totals
        if issue_register_records.data:
            for rec in issue_register_records.data:
                try:
                    total_issued_qty += float(rec.get('quantity_issued', rec.get('quantity', 0) or 0))
                except Exception:
                    try:
                        total_issued_qty += float(rec.get('quantity', 0) or 0)
                    except Exception:
                        pass
        
        # Calculate utilized and scrapped values using cost mapping
        if utilization_records.data:
            for record in utilization_records.data:
                qty = float(record.get('quantity', 0) or 0)
                raw_part = record.get('part_no')
                try:
                    part_key = str(raw_part).strip().lower()
                except Exception:
                    part_key = str(raw_part)
                total_utilized_qty += qty
                # Add to utilized value using cost per unit for this part
                if part_key in cost_per_unit_map:
                    utilized_value += qty * cost_per_unit_map[part_key]

        if scrap_records.data:
            for record in scrap_records.data:
                qty = float(record.get('quantity', 0) or 0)
                raw_part = record.get('part_no')
                try:
                    part_key = str(raw_part).strip().lower()
                except Exception:
                    part_key = str(raw_part)
                total_scrapped_qty += qty
                # Add to scrapped value using cost per unit for this part
                if part_key in cost_per_unit_map:
                    scrapped_value += qty * cost_per_unit_map[part_key]
        
        # Calculate final totals using balance formula:
        # Original Received = Current In-Stock + Utilized + Scrapped + Issued
        original_received_qty = total_current_qty + total_utilized_qty + total_scrapped_qty + total_issued_qty
        final_available_qty = total_current_qty  # current in-stock (purchases.quantity reflects remaining)
        final_instock_value = total_value_all_purchases - utilized_value - scrapped_value

        # Fetch corrected maintenance job cards to show in Maintenance Utilization section
        try:
            maint_res = supabase.table('maintenance_entry').select('*').eq('status', 'corrected').order('updated_at', desc=True).execute()
            maintenance_corrected = maint_res.data if maint_res.data else []
        except Exception:
            maintenance_corrected = []

        # Enrich corrected maintenance entries with total utilized qty from material_utilization
        try:
            util_res = supabase.table('material_utilization').select('entry_no, description, quantity').execute()
            util_rows = util_res.data if util_res.data else []
            util_map = {}
            import re
            for u in util_rows:
                try:
                    qty = float(u.get('quantity') or 0)
                except Exception:
                    qty = 0
                desc = (u.get('description') or '')
                entry_no_u = (u.get('entry_no') or '')
                mid = None
                m = re.search(r'From maintenance\s*(\d+)', desc)
                if m:
                    try:
                        mid = int(m.group(1))
                    except Exception:
                        mid = None
                else:
                    m2 = re.search(r'MU/(\d+)/', entry_no_u)
                    if m2:
                        try:
                            mid = int(m2.group(1))
                        except Exception:
                            mid = None
                if mid is not None:
                    util_map[mid] = util_map.get(mid, 0) + qty

            for e in maintenance_corrected:
                try:
                    eid = int(e.get('id')) if e.get('id') is not None else None
                except Exception:
                    eid = None
                # default to 0 so the template shows the entered value instead of blank/None
                e['utilized_qty'] = util_map.get(eid, 0)
        except Exception:
            pass

        # Also fetch pending maintenance job cards so the UI can show them when requested
        try:
            maint_pending_res = supabase.table('maintenance_entry').select('*').eq('status', 'pending').order('updated_at', desc=True).execute()
            maintenance_pending = maint_pending_res.data if maint_pending_res.data else []
            for e in maintenance_pending:
                try:
                    eid = int(e.get('id')) if e.get('id') is not None else None
                except Exception:
                    eid = None
                e['utilized_qty'] = util_map.get(eid, 0)
        except Exception:
            maintenance_pending = []

        # Use centralized stock totals helper so displayed totals match API/dashboard
        try:
            stock_totals = get_stock_totals()
        except Exception:
            stock_totals = None

        # Fallback to previously computed values if helper fails
        total_items_val = round(original_received_qty, 2) if stock_totals is None else stock_totals.get('total_original_received_qty', round(original_received_qty, 2))
        active_items_val = round(final_available_qty, 2) if stock_totals is None else stock_totals.get('total_current_qty', round(final_available_qty, 2))
        total_value_val = (f"{total_value_all_purchases:,.2f}") if stock_totals is None else f"{stock_totals.get('total_purchase_value', 0.0):,.2f}"
        total_utilized_val = round(total_utilized_qty, 2) if stock_totals is None else stock_totals.get('total_utilized_qty', round(total_utilized_qty, 2))
        total_scrapped_val = round(total_scrapped_qty, 2) if stock_totals is None else stock_totals.get('total_scrapped_qty', round(total_scrapped_qty, 2))
        instock_value_val = (f"{final_instock_value:,.2f}") if stock_totals is None else f"{stock_totals.get('instock_value', 0.0):,.2f}"
        utilized_value_val = (f"{utilized_value:,.2f}") if stock_totals is None else f"{stock_totals.get('utilized_value', 0.0):,.2f}"
        scrapped_value_val = (f"{scrapped_value:,.2f}") if stock_totals is None else f"{stock_totals.get('scrapped_value', 0.0):,.2f}"

        return render_template('stock_inventory.html', 
                             items=available_items,
                             issued_items=issued_items.data,
                             utilization_records=utilization_records.data if utilization_records.data else [],
                             scrap_records=scrap_records.data if scrap_records.data else [],
                             maintenance_corrected=maintenance_corrected,
                             maintenance_pending=maintenance_pending,
                             total_items=total_items_val,  # Original total quantity received
                             active_items=active_items_val,  # Current in-stock quantity
                             total_value=total_value_val,  # Total value of ALL purchases
                             total_utilized=total_utilized_val,
                             total_scrapped=total_scrapped_val,
                             instock_value=instock_value_val,
                             utilized_value=utilized_value_val,
                             scrapped_value=scrapped_value_val,
                             vendors=sorted(vendors),
                             purchase_types=sorted(purchase_types))
    except Exception as e:
        flash(f'Error loading inventory: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/api/stock-totals')
@login_required
def api_stock_totals():
    """Return authoritative stock totals computed from purchases, utilization, scrap and issue registers."""
    try:
        totals = get_stock_totals()
        # Mirror the previous JSON structure but with numeric values where appropriate
        result = {
            'total_original_received_qty': totals.get('total_original_received_qty', 0.0),
            'total_current_qty': totals.get('total_current_qty', 0.0),
            'total_utilized_qty': totals.get('total_utilized_qty', 0.0),
            'total_scrapped_qty': totals.get('total_scrapped_qty', 0.0),
            'total_issued_qty': totals.get('total_issued_qty', 0.0),
            'closing_stock_qty': totals.get('closing_stock_qty', 0.0),
            'total_purchase_value': f"{totals.get('total_purchase_value', 0.0):,.2f}",
            'instock_value': f"{totals.get('instock_value', 0.0):,.2f}",
            'utilized_value': f"{totals.get('utilized_value', 0.0):,.2f}",
            'scrapped_value': f"{totals.get('scrapped_value', 0.0):,.2f}"
        }
        return jsonify({'success': True, 'totals': result}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/issue-stock-form', methods=['GET', 'POST'])
@login_required
def issue_stock_form():
    """Display form to issue stock items"""
    if request.method == 'POST':
        try:
            # Get form data
            issue_data = {
                'entry_no': request.form.get('entry_no'),
                'purchase_id': request.form.get('purchase_id'),
                'part_no': request.form.get('part_no'),
                'part_name': request.form.get('part_name'),
                'vehicle_no': request.form.get('vehicle_no'),
                'vehicle_id': request.form.get('vehicle_id'),
                'date': request.form.get('date'),
                'time': request.form.get('time'),
                'kilometer': request.form.get('kilometer'),
                'issuing_person_name': request.form.get('issuing_person_name'),
                'driver_responsible': request.form.get('driver_responsible'),
                'mechanic_responsible': request.form.get('mechanic_responsible'),
                'comments': request.form.get('comments'),
                'status': 'issued'
            }
            
            # Save to stock_issue_register table
            result = supabase.table('stock_issue_register').insert(issue_data).execute()
            
            if result.data:
                # Update purchase item status to 'issued'
                supabase.table('purchases').update({'status': 'issued'}).eq('id', issue_data['purchase_id']).execute()
                flash('Stock issued successfully!', 'success')
                return redirect(url_for('stock_inventory'))
            else:
                flash('Error issuing stock.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    # GET request - show form
    try:
        # Get next entry number
        entry_no_result = supabase.rpc('get_next_stock_issue_entry_no').execute()
        entry_no = entry_no_result.data if entry_no_result.data else '001'
        
        # Get all active purchase items
        items = supabase.table('purchases').select('*').eq('status', 'active').order('created_at', desc=True).execute()
        
        return render_template('stock_issue.html', 
                             entry_no=entry_no,
                             items=items.data)
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'danger')
        return redirect(url_for('stock_inventory'))

@app.route('/issue-stock/<item_id>', methods=['POST'])
@login_required
def issue_stock(item_id):
    """Quick issue - redirect to issue form with item pre-selected"""
    return redirect(url_for('issue_stock_form') + f'?item_id={item_id}')

@app.route('/stock-issue-history')
@login_required
def stock_issue_history():
    """Display all stock issue records"""
    try:
        records = supabase.table('stock_issue_register').select('*').order('created_at', desc=True).execute()
        return render_template('stock_issue_history.html', records=records.data)
    except Exception as e:
        flash(f'Error loading issue history: {str(e)}', 'danger')
        return redirect(url_for('stock_inventory'))

@app.route('/fuel', methods=['GET', 'POST'])
@login_required
@module_required('Fuel')
def fuel():
    timings = {}
    t0 = time.perf_counter()
    if request.method == 'POST':
        # Calculate distance traveled and fuel mileage (efficiency)
        previous_km = float(request.form.get('previous_km', 0) or 0)
        current_km = float(request.form.get('current_km', 0) or 0)
        quantity = float(request.form.get('quantity', 0) or 0)
        distance_traveled = current_km - previous_km
        mileage_per_liter = distance_traveled / quantity if quantity > 0 else 0
        
        # Collect form data
        data = {
            'date': request.form.get('date', ''),
            'time': request.form.get('time', ''),
            'entry_no': request.form.get('entry_no', ''),
            'bill_no': request.form.get('bill_no', ''),
            'type_of_purchase': request.form.get('type_of_purchase', ''),
            'part_no': request.form.get('part_no', ''),
            'part_name': request.form.get('part_name', ''),
            'quantity': request.form.get('quantity', ''),
            'rate': request.form.get('rate', ''),
            'amount': request.form.get('amount', ''),
            'route_id': request.form.get('route_id', ''),
            'vehicle_id': request.form.get('vehicle_id', ''),
            'vehicle_no': request.form.get('vehicle_no', ''),
            'vehicle_reg_no': request.form.get('vehicle_no', ''),
            'previous_km': previous_km,
            'current_km': current_km,
            'km_reading': current_km,
            'mileage': distance_traveled,  # DB column 'mileage' stores distance traveled
            'mileage_per_liter': mileage_per_liter,
            'driver': request.form.get('driver', ''),
            'user_id': session.get('user_id')
        }
        
        # Save to database
        result = save_fuel(data)
        
        if result:
            # If a part_no was provided (e.g., Engine oil), consume from purchases FIFO
            try:
                part_no = data.get('part_no')
                qty_to_consume = float(data.get('quantity') or 0)
                ttype = (data.get('type_of_purchase') or '').lower()
                # Only attempt consumption for parts (engine oil or other stocked items)
                if part_no and qty_to_consume > 0:
                    # allow consumption for engine oil and other stocked parts
                    if 'engine' in ttype or 'oil' in ttype or True:
                        try:
                            consume_res = consume_part_from_purchases(part_no, qty_to_consume)
                            app.logger.debug('consume_part_from_purchases result for fuel: %s', consume_res)
                        except Exception as exc2:
                            app.logger.exception('Error during consume_part_from_purchases for %s: %s', part_no, exc2)
            except Exception:
                app.logger.exception('Error while attempting to consume part for fuel')

            flash('Fuel record saved successfully!', 'success')
            return redirect(url_for('fuel', success='true'))
        else:
            flash('Error saving fuel record. Please try again.', 'danger')
    
    t_post = time.perf_counter()
    timings['post_handling_ms'] = int((t_post - t0) * 1000)

    next_entry_no = get_next_fuel_entry_no()
    t_after_next_entry = time.perf_counter()
    timings['next_entry_no_ms'] = int((t_after_next_entry - t_post) * 1000)
    
    # Get all vehicles for dropdown
    try:
        t_veh_start = time.perf_counter()
        vehicles = supabase.table('vehicles').select('vehicle_id, registration_no').order('vehicle_id').execute()
        vehicles_data = vehicles.data if vehicles.data else []
        t_veh_end = time.perf_counter()
        timings['vehicles_fetch_ms'] = int((t_veh_end - t_veh_start) * 1000)
    except Exception as e:
        app.logger.exception('Error fetching vehicles for fuel form')
        vehicles_data = []
        timings['vehicles_fetch_ms'] = 0
    
    # Get last KM reading for each vehicle grouped by fuel type
    # NOTE: avoid doing one Supabase query per vehicle-per-fuel-type (n*5 queries) which is slow.
    # Instead, fetch a small recent set of fuel rows per vehicle and derive the most recent
    # value for each fuel type locally (1 query per vehicle).
    vehicle_last_km = {}
    try:
        # Batch approach: fetch recent fuel rows once and derive latest km per vehicle+fuel_type.
        fuel_types = ['DIESEL', 'PETROL', 'Adblue', 'Engine oil', 'OTHERS']
        t_vlk_start = time.perf_counter()

        # initialize map for vehicles present
        for vehicle in vehicles_data:
            vid = vehicle.get('vehicle_id')
            if vid:
                vehicle_last_km[vid] = {ft: 0 for ft in fuel_types}

        # Fetch recent fuel entries globally (limit tuned to expected activity)
        recent = supabase.table('fuel').select('vehicle_id,current_km,type_of_purchase,created_at').order('created_at', desc=True).limit(2000).execute()
        rows = recent.data if recent.data else []

        # For each row in descending time order, first-seen vehicle+fuel_type is the latest
        seen = {}
        for r in rows:
            vid = r.get('vehicle_id')
            if not vid or vid not in vehicle_last_km:
                continue
            ft = (r.get('type_of_purchase') or '').strip()
            if not ft:
                continue
            key = f"{vid}||{ft}"
            if key in seen:
                continue
            km = r.get('current_km')
            try:
                vehicle_last_km[vid][ft] = float(km) if km is not None else 0
            except Exception:
                vehicle_last_km[vid][ft] = 0
            seen[key] = True

        t_vlk_end = time.perf_counter()
        timings['vehicle_last_km_total_ms'] = int((t_vlk_end - t_vlk_start) * 1000)
    except Exception as e:
        print(f"Error fetching last KM: {e}")
        vehicle_last_km = {}
    
    # Get all parts for dropdown
    try:
        t_parts_start = time.perf_counter()
        parts = supabase.table('parts').select('part_id, part_name').eq('status', 'active').order('part_name').execute()
        parts_data = parts.data if parts.data else []
        t_parts_end = time.perf_counter()
        timings['parts_fetch_ms'] = int((t_parts_end - t_parts_start) * 1000)
    except Exception:
        parts_data = []
        timings['parts_fetch_ms'] = 0

    # Render and attach timings in a response header for quick diagnostics
    t_render_start = time.perf_counter()
    rendered = render_template('fuel.html', entry_no=next_entry_no, vehicles=vehicles_data, parts=parts_data, vehicle_last_km=vehicle_last_km)
    t_render_end = time.perf_counter()
    timings['render_ms'] = int((t_render_end - t_render_start) * 1000)
    timings['total_ms'] = int((t_render_end - t0) * 1000)

    # log timings
    try:
        app.logger.debug('Fuel page timings: %s', json.dumps(timings))
    except Exception:
        pass

    from flask import make_response
    resp = make_response(rendered)
    try:
        resp.headers['X-Page-Timings'] = json.dumps(timings)
    except Exception:
        pass
    return resp

@app.route('/statutory', methods=['GET', 'POST'])
@login_required
@module_required('Statutory')
def statutory():
    if request.method == 'POST':
        selected_vehicle_id = (request.form.get('vehicle_id') or '').strip()
        selected_registration_no = (request.form.get('registration_no') or '').strip()
        selected_transaction = (request.form.get('type_of_transaction') or '').strip()
        selected_validity_date = (request.form.get('validity_date') or request.form.get('registration_validity') or '').strip()

        # Collect form data
        data = {
            'date': request.form.get('date', ''),
            'time': request.form.get('time', ''),
            'entry_no': request.form.get('entry_no', ''),
            'vehicle_id': selected_vehicle_id,
            'registration_no': selected_registration_no,
            'invoice_no': request.form.get('invoice_no', ''),
            'invoice_date': request.form.get('invoice_date', ''),
            'statutory_body_id': request.form.get('statutory_body_id', ''),
            'type_of_transaction': request.form.get('type_of_transaction', ''),
            'validity_date': request.form.get('validity_date', ''),
            'rate': request.form.get('rate', ''),
            'taxable_amount': request.form.get('taxable_amount', ''),
            'sgst_percent': request.form.get('sgst_percent', ''),
            'sgst_amount': request.form.get('sgst_amount', ''),
            'cgst_percent': request.form.get('cgst_percent', ''),
            'cgst_amount': request.form.get('cgst_amount', ''),
            'igst_percent': request.form.get('igst_percent', ''),
            'igst_amount': request.form.get('igst_amount', ''),
            'total_amount': request.form.get('total_amount', ''),
            'entered_by': request.form.get('entered_by', ''),
            'approved_by': request.form.get('approved_by', ''),
            'approver_name': request.form.get('approver_name', ''),
            'rejection_reason': request.form.get('rejection_reason', ''),
            'user_id': session.get('user_id')
        }
        
        # Save to database
        result = save_statutory(data)
        
        if result:
            # Sync statutory validity to vehicle master so admin edit page reflects the latest value.
            validity_field_map = {
                'Road Tax': 'tax_validity',
                'Insurance': 'insurance_validity',
                'Permit': 'permit_validity',
                'Fitness Certificate': 'fitness_validity',
                'Pollution Certificate': 'pucc_validity',
                'Registration': 'registration_validity'
            }

            vehicle_patch = {}
            mapped_field = validity_field_map.get(selected_transaction)
            if mapped_field and selected_validity_date:
                vehicle_patch[mapped_field] = selected_validity_date
            if selected_registration_no:
                vehicle_patch['registration_no'] = selected_registration_no

            if selected_vehicle_id and vehicle_patch:
                try:
                    vehicle_row = get_vehicle_by_vehicle_id(selected_vehicle_id)
                    if not vehicle_row and selected_vehicle_id.isdigit():
                        vehicle_row = get_vehicle_by_id(int(selected_vehicle_id))

                    if vehicle_row and vehicle_row.get('id'):
                        updated_vehicle = admin_update_vehicle(vehicle_row.get('id'), vehicle_patch)
                        if updated_vehicle:
                            flash('Linked vehicle validity updated in admin vehicle records.', 'success')
                            # Send immediate SMTP notification for statutory-driven validity change.
                            if mapped_field and selected_validity_date:
                                try:
                                    from datetime import date as _date
                                    settings = get_settings() or {}
                                    if settings.get('immediate_enabled', True):
                                        recipients = settings.get('recipients') or None
                                        merged_vehicle = {}
                                        if isinstance(vehicle_row, dict):
                                            merged_vehicle.update(vehicle_row)
                                        merged_vehicle.update(vehicle_patch)
                                        parsed = parse_date_str(selected_validity_date)
                                        try:
                                            days_left = (parsed - _date.today()).days if parsed else None
                                        except Exception:
                                            days_left = None
                                        label = VEHICLE_DATE_FIELDS.get(mapped_field, mapped_field)
                                        subj, body = format_vehicle_reminder(
                                            merged_vehicle,
                                            label,
                                            days_left if days_left is not None else 'N/A',
                                            due_date_iso=(parsed.isoformat() if parsed else None)
                                        )
                                        sent = send_email(subj, body, to_addrs=recipients)
                                        if not sent:
                                            flash('Vehicle updated, but SMTP email was not sent. Check reminder recipients/SMTP settings.', 'warning')
                                except Exception:
                                    app.logger.exception('Failed to send statutory immediate email notification')
                        else:
                            flash('Statutory saved, but vehicle update failed.', 'warning')
                    else:
                        flash('Statutory saved, but selected vehicle was not found for update.', 'warning')
                except Exception as sync_err:
                    app.logger.exception('Failed syncing statutory validity to vehicle')
                    flash(f'Statutory saved, but vehicle sync failed: {sync_err}', 'warning')

            flash('Statutory record saved successfully!', 'success')
            return redirect(url_for('statutory', success='true'))
        else:
            flash('Error saving statutory record. Please try again.', 'danger')
    
    next_entry_no = get_next_statutory_entry_no()
    # Provide vehicle list so the statutory form can show vehicle choices
    try:
        vehicles = get_all_vehicles() or []
    except Exception:
        vehicles = []
    return render_template('statutory.html', entry_no=next_entry_no, vehicles=vehicles)

@app.route('/trip-sheet', methods=['GET', 'POST'])
@login_required
@module_required('Trip Sheet')
def trip_sheet():
    """Trip Sheet form for recording trip details"""
    if request.method == 'POST':
        try:
            # Calculate totals
            student_male = int(request.form.get('student_male', 0) or 0)
            student_female = int(request.form.get('student_female', 0) or 0)
            student_transgender = int(request.form.get('student_transgender', 0) or 0)
            student_total = student_male + student_female + student_transgender
            
            faculty_male = int(request.form.get('faculty_male', 0) or 0)
            faculty_female = int(request.form.get('faculty_female', 0) or 0)
            faculty_transgender = int(request.form.get('faculty_transgender', 0) or 0)
            faculty_total = faculty_male + faculty_female + faculty_transgender
            
            guest_male = int(request.form.get('guest_male', 0) or 0)
            guest_female = int(request.form.get('guest_female', 0) or 0)
            guest_transgender = int(request.form.get('guest_transgender', 0) or 0)
            guest_total = guest_male + guest_female + guest_transgender
            
            cumulative_strength = student_total + faculty_total + guest_total
            
            # Collect form data
            data = {
                'date_time': request.form.get('date_time'),
                'route_id': request.form.get('route_id'),
                'driver_id': request.form.get('driver_id'),
                'driver_name': request.form.get('driver_name'),
                'vehicle_id': request.form.get('vehicle_id'),
                'vehicle_no': request.form.get('vehicle_no'),
                'trip_start_km': request.form.get('trip_start_km'),
                'trip_close_km': request.form.get('trip_close_km'),
                'trip_start_time': request.form.get('trip_start_time'),
                'trip_close_time': request.form.get('trip_close_time'),
                'student_male': student_male,
                'student_female': student_female,
                'student_transgender': student_transgender,
                'student_total': student_total,
                'faculty_male': faculty_male,
                'faculty_female': faculty_female,
                'faculty_transgender': faculty_transgender,
                'faculty_total': faculty_total,
                'guest_male': guest_male,
                'guest_female': guest_female,
                'guest_transgender': guest_transgender,
                'guest_total': guest_total,
                'cumulative_strength': cumulative_strength,
                'trip_start_place': request.form.get('trip_start_place'),
                'trip_close_place': request.form.get('trip_close_place'),
                'comments': request.form.get('comments'),
                'entered_by': request.form.get('entered_by')
            }
            
            # Save to trip_sheet table
            result = supabase.table('trip_sheet').insert(data).execute()
            
            if result.data:
                flash('Trip sheet submitted successfully!', 'success')
                return redirect(url_for('trip_sheet'))
            else:
                flash('Error submitting trip sheet.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    # GET request - show form
    try:
        # Get all vehicles for dropdown
        vehicles = supabase.table('vehicles').select('vehicle_id, registration_no').order('vehicle_id').execute()
        return render_template('trip_sheet.html', vehicles=vehicles.data)
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/home')
@login_required
def home():
    user_name = session.get('user_name', 'USER')
    return render_template('home.html', user=session.get('user'), user_role=user_name)

@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():
    from datetime import datetime, timedelta
    
    users_count = get_users_count()
    vehicles_count = get_vehicles_count()
    
    # Get statutory records and check for upcoming due dates
    statutory_records = get_all_statutory_records()
    today = datetime.now().date()
    due_soon_alerts = []
    
    for record in statutory_records:
        if record.get('validity_date'):
            try:
                # Parse validity_date
                validity_date_str = str(record.get('validity_date'))
                if 'T' in validity_date_str:
                    validity_date = datetime.fromisoformat(validity_date_str.split('T')[0]).date()
                else:
                    validity_date = datetime.strptime(validity_date_str.split(' ')[0], '%Y-%m-%d').date()
                
                days_remaining = (validity_date - today).days
                
                # Alert if due within 7 days or overdue
                if days_remaining <= 7:
                    alert_type = 'overdue' if days_remaining < 0 else 'warning'
                    vehicle_id = record.get('vehicle_id') or record.get('statutory_body_id') or 'Unknown'
                    registration_no = record.get('registration_no') or 'N/A'
                    due_soon_alerts.append({
                        'statutory_body_id': record.get('statutory_body_id', 'Unknown'),
                        'vehicle_id': vehicle_id,
                        'registration_no': registration_no,
                        'record_type': record.get('type_of_transaction', 'Statutory'),
                        'next_due': validity_date.strftime('%d-%m-%Y'),
                        'days_remaining': days_remaining,
                        'alert_type': alert_type
                    })
            except Exception as e:
                print(f"Error parsing date for record: {e}")
                continue
    
    # Sort by days remaining (most urgent first)
    due_soon_alerts.sort(key=lambda x: x['days_remaining'])
    
    # Get inventory items count from purchases
    try:
        purchases_response = supabase.table('purchases').select('id').eq('status', 'active').execute()
        inventory_count = len(purchases_response.data) if purchases_response.data else 0
    except:
        inventory_count = 0
    
    return render_template('admin_dashboard.html', 
                           admin=session.get('admin'),
                           users_count=users_count,
                           vehicles_count=vehicles_count,
                           reports_count=inventory_count,
                           due_soon_alerts=due_soon_alerts)

@app.route('/admin/reports')
@admin_required
def admin_reports():
    """Admin reports page showing fuel, statutory, and trip sheet records"""
    try:
        # Fetch all records
        fuel_records = get_all_fuel_records()
        statutory_records = get_all_statutory_records()
        # Also include vehicle-level validity fields (from vehicle page) as synthetic
        # statutory-like records so compliance status reflects both sources.
        try:
            vehicle_rows = get_all_vehicles() or []
        except Exception:
            vehicle_rows = []
        # Build synthetic records from vehicles for known validity fields
        veh_stat_rows = []
        for v in vehicle_rows:
            vid = v.get('vehicle_id') or v.get('id') or v.get('vehicle_id_value') or ''
            reg = v.get('registration_no') or v.get('registration') or ''
            for field_key, label in VEHICLE_DATE_FIELDS.items():
                if v.get(field_key):
                    veh_stat_rows.append({
                        'type_of_transaction': label,
                        'vehicle_id': vid,
                        'registration_no': reg,
                        'validity_date': v.get(field_key),
                        'source': 'vehicle_record'
                    })
        # treat statutory_records list as possibly None
        statutory_records = (statutory_records or []) + veh_stat_rows
        trip_records = list(get_all_trip_sheets())
        
        # Calculate summaries
        fuel_total_liters = sum(float(r.get('quantity', 0) or 0) for r in fuel_records)
        fuel_total_amount = sum(float(r.get('amount', 0) or 0) for r in fuel_records)
        
        statutory_total_amount = sum(float(r.get('total_amount', 0) or 0) for r in statutory_records)
        
        trip_total_distance = sum(float(r.get('trip_distance', 0) or 0) for r in trip_records)
        trip_total_passengers = sum(int(r.get('total_strength', 0) or 0) for r in trip_records)
        
        return render_template('admin_reports.html',
                             fuel_records=fuel_records,
                             fuel_total_liters=fuel_total_liters,
                             fuel_total_amount=fuel_total_amount,
                             statutory_records=statutory_records,
                             statutory_total_amount=statutory_total_amount,
                             trip_records=trip_records,
                             trip_total_distance=trip_total_distance,
                             trip_total_passengers=trip_total_passengers)
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/trip-records')
@admin_required
def admin_trip_records():
    """Admin trip records page with filters"""
    from datetime import datetime
    import html
    import urllib.parse
    import re
    
    def clean_text(text):
        """Clean up corrupted/encoded text like '& %¶& &k&a&m&a&n&d&o&d' -> 'Kamandod'"""
        if not text:
            return '-'
        try:
            text = str(text)
            
            # Check for the pattern: characters separated by &
            # Pattern like "&k&a&m&a&n&d&o&d" or "& %¶& &k&a&m&a&n&d&o&d"
            if '&' in text:
                # Remove common garbage prefixes
                text = re.sub(r'^[&\s%¶]+', '', text)
                
                # Check if it's the pattern of single chars separated by &
                parts = text.split('&')
                # If most parts are single characters, it's the corrupted pattern
                single_char_parts = [p.strip() for p in parts if len(p.strip()) == 1]
                if len(single_char_parts) >= len(parts) * 0.7:  # 70% are single chars
                    # Join the single characters
                    cleaned = ''.join([p.strip() for p in parts if p.strip()])
                    return cleaned.title() if cleaned else '-'
            
            # Normal text - just return as is
            return text
        except:
            return str(text) if text else '-'
    
    try:
        # Get filter parameters
        route_filter = request.args.get('route_id', '')
        vehicle_filter = request.args.get('vehicle_id', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Fetch all trip records (ensure we have a list, not a generator)
        trip_records = list(get_all_trip_sheets())
        
        # Apply filters
        if route_filter:
            trip_records = [r for r in trip_records if (r.get('route_id') or '').lower() == route_filter.lower()]
        
        if vehicle_filter:
            trip_records = [r for r in trip_records if (r.get('vehicle_id') or '').lower() == vehicle_filter.lower()]
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                trip_records = [r for r in trip_records if r.get('date_time') and datetime.fromisoformat(r['date_time'].replace('Z', '+00:00').split('+')[0]) >= date_from_obj]
            except:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                trip_records = [r for r in trip_records if r.get('date_time') and datetime.fromisoformat(r['date_time'].replace('Z', '+00:00').split('+')[0]) <= date_to_obj]
            except:
                pass
        
        # Clean up corrupted text in trip records
        for record in trip_records:
            record['trip_start_place'] = clean_text(record.get('trip_start_place'))
            record['trip_close_place'] = clean_text(record.get('trip_close_place'))
        
        # Get unique values for filter dropdowns
        all_records = list(get_all_trip_sheets())
        unique_routes = sorted(set(r.get('route_id', '') for r in all_records if r.get('route_id')))
        unique_vehicles = sorted(set(r.get('vehicle_id', '') for r in all_records if r.get('vehicle_id')))
        
        # Calculate totals
        total_trips = len(trip_records)
        total_distance = sum(float(r.get('trip_close_km', 0) or 0) - float(r.get('trip_start_km', 0) or 0) for r in trip_records)

        # Compute totals with fallbacks: some historical records may store per-gender counts
        def safe_int(val):
            try:
                return int(val or 0)
            except Exception:
                try:
                    return int(float(str(val).replace(',', '').strip()))
                except Exception:
                    return 0

        total_students = 0
        total_faculty = 0
        total_guests = 0
        total_passengers = 0
        for r in trip_records:
            # students: prefer `student_total`, else sum gender fields
            s = safe_int(r.get('student_total'))
            if not s:
                s = safe_int(r.get('student_male')) + safe_int(r.get('student_female')) + safe_int(r.get('student_transgender'))
            total_students += s

            # faculty
            f = safe_int(r.get('faculty_total'))
            if not f:
                f = safe_int(r.get('faculty_male')) + safe_int(r.get('faculty_female')) + safe_int(r.get('faculty_transgender'))
            total_faculty += f

            # guests
            g = safe_int(r.get('guest_total'))
            if not g:
                g = safe_int(r.get('guest_male')) + safe_int(r.get('guest_female')) + safe_int(r.get('guest_transgender'))
            total_guests += g

            # passengers: cumulative_strength/total_strength preferred, else male/female/transgender totals
            p = safe_int(r.get('cumulative_strength') or r.get('total_strength'))
            if not p:
                p = safe_int(r.get('male_count')) + safe_int(r.get('female_count')) + safe_int(r.get('transgender_count'))
            total_passengers += p
        
        # Compute daily and monthly averages (based on currently filtered trip_records)
        unique_dates = set()
        monthly_counts = {}
        for r in trip_records:
            dt = r.get('date_time')
            if not dt:
                continue
            try:
                date_str = str(dt)[:10]
            except:
                continue
            unique_dates.add(date_str)
            month_key = date_str[:7]  # YYYY-MM
            monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

        days_with_entries = len(unique_dates)
        months_with_entries = len(monthly_counts)
        daily_avg = (total_trips / days_with_entries) if days_with_entries else 0
        monthly_avg = (total_trips / months_with_entries) if months_with_entries else 0

        # Always base per-day averages on actual days that have entries (not calendar days).
        # This ensures a 30-day range where only 20 days have records shows avg over 20 days.
        days_for_avg = days_with_entries if days_with_entries else 1
        avg_range_label = f"{days_with_entries} days with entries" if days_with_entries else 'no range'

        # Per-day averages (based on filter range when available)
        avg_trips_per_day = (total_trips / days_for_avg) if days_for_avg else 0
        avg_km_per_day = (total_distance / days_for_avg) if days_for_avg else 0
        avg_students_per_day = (total_students / days_for_avg) if days_for_avg else 0
        avg_faculty_per_day = (total_faculty / days_for_avg) if days_for_avg else 0
        avg_guests_per_day = (total_guests / days_for_avg) if days_for_avg else 0
        avg_passengers_per_day = (total_passengers / days_for_avg) if days_for_avg else 0

        # Aggregate monthly sums for additional metrics (trips, km, students, faculty, guests, passengers)
        monthly_agg = {}
        for r in trip_records:
            dt = r.get('date_time')
            if not dt:
                continue
            try:
                date_str = str(dt)[:10]
            except:
                continue
            month_key = date_str[:7]
            if month_key not in monthly_agg:
                monthly_agg[month_key] = {
                    'trips': 0,
                    'km': 0.0,
                    'students': 0,
                    'faculty': 0,
                    'guests': 0,
                    'passengers': 0
                }
            m = monthly_agg[month_key]
            m['trips'] += 1
            try:
                start_km = float(r.get('trip_start_km') or 0)
            except:
                start_km = 0.0
            try:
                close_km = float(r.get('trip_close_km') or 0)
            except:
                close_km = 0.0
            m['km'] += max(0.0, close_km - start_km)

            # students
            try:
                students = int(r.get('student_total') or 0)
            except:
                students = 0
            if not students:
                try:
                    students = int(r.get('student_male') or 0) + int(r.get('student_female') or 0) + int(r.get('student_transgender') or 0)
                except:
                    students = students or 0
            m['students'] += students

            # faculty
            try:
                faculty = int(r.get('faculty_total') or 0)
            except:
                faculty = 0
            if not faculty:
                try:
                    faculty = int(r.get('faculty_male') or 0) + int(r.get('faculty_female') or 0) + int(r.get('faculty_transgender') or 0)
                except:
                    faculty = faculty or 0
            m['faculty'] += faculty

            # guests
            try:
                guests = int(r.get('guest_total') or 0)
            except:
                guests = 0
            if not guests:
                try:
                    guests = int(r.get('guest_male') or 0) + int(r.get('guest_female') or 0) + int(r.get('guest_transgender') or 0)
                except:
                    guests = guests or 0
            m['guests'] += guests

            # passengers (cumulative_strength/total_strength or male/female/transgender counts)
            try:
                passengers = int(r.get('cumulative_strength') or r.get('total_strength') or 0)
            except:
                passengers = 0
            if not passengers:
                try:
                    passengers = int(r.get('male_count') or 0) + int(r.get('female_count') or 0) + int(r.get('transgender_count') or 0)
                except:
                    passengers = passengers or 0
            m['passengers'] += passengers

        # Prepare sorted lists for template
        monthly_counts_items = sorted(monthly_counts.items(), reverse=True)
        monthly_aggregates_items = sorted(monthly_agg.items(), reverse=True)

        # Compute averages across months
        if months_with_entries:
            avg_trips_per_month = sum(m['trips'] for m in monthly_agg.values()) / months_with_entries
            avg_km_per_month = sum(m['km'] for m in monthly_agg.values()) / months_with_entries
            avg_students_per_month = sum(m['students'] for m in monthly_agg.values()) / months_with_entries
            avg_faculty_per_month = sum(m['faculty'] for m in monthly_agg.values()) / months_with_entries
            avg_guests_per_month = sum(m['guests'] for m in monthly_agg.values()) / months_with_entries
            avg_passengers_per_month = sum(m['passengers'] for m in monthly_agg.values()) / months_with_entries
        else:
            avg_trips_per_month = avg_km_per_month = avg_students_per_month = avg_faculty_per_month = avg_guests_per_month = avg_passengers_per_month = 0

        # Get all vehicles for dropdown
        vehicles = supabase.table('vehicles').select('vehicle_id, registration_no').order('vehicle_id').execute()
        
        return render_template('admin_trip_records.html',
                             trip_records=trip_records,
                             unique_routes=unique_routes,
                             unique_vehicles=unique_vehicles,
                             vehicles=vehicles.data,
                             route_filter=route_filter,
                             vehicle_filter=vehicle_filter,
                             date_from=date_from,
                             date_to=date_to,
                             total_trips=total_trips,
                             total_distance=total_distance,
                             total_students=total_students,
                             total_faculty=total_faculty,
                             total_guests=total_guests,
                             total_passengers=total_passengers,
                             daily_avg=daily_avg,
                             monthly_avg=monthly_avg,
                             monthly_counts=monthly_counts_items,
                             monthly_aggregates=monthly_aggregates_items,
                             avg_trips_per_month=avg_trips_per_month,
                             avg_km_per_month=avg_km_per_month,
                             avg_students_per_month=avg_students_per_month,
                             avg_faculty_per_month=avg_faculty_per_month,
                             avg_guests_per_month=avg_guests_per_month,
                             avg_passengers_per_month=avg_passengers_per_month,
                             avg_trips_per_day=avg_trips_per_day,
                             avg_km_per_day=avg_km_per_day,
                             avg_students_per_day=avg_students_per_day,
                             avg_faculty_per_day=avg_faculty_per_day,
                             avg_guests_per_day=avg_guests_per_day,
                             avg_passengers_per_day=avg_passengers_per_day,
                             avg_range_label=avg_range_label,
                             unique_days=days_with_entries,
                             months_count=months_with_entries)
    except Exception as e:
        flash(f'Error loading trip records: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/trips/add')
@admin_required
def admin_add_trip():
    """Redirect helper for templates linking to add-trip page."""
    # The application uses `trip_sheet` for creating new trip entries.
    # Keep a dedicated endpoint so templates can call `url_for('admin_add_trip')`.
    try:
        return redirect(url_for('trip_sheet'))
    except Exception:
        return redirect(url_for('admin_trip_records'))

@app.route('/admin/analytics-dashboard')
@admin_required
def admin_analytics_dashboard():
    """Analytics dashboard with charts and graphical reports"""
    from datetime import datetime, timedelta
    from collections import defaultdict
    import re
    
    def parse_datetime(dt_string):
        """Helper function to parse datetime strings with various formats"""
        try:
            if not dt_string:
                return None
            dt_str = str(dt_string).strip()
            
            # Try using python-dateutil if available
            try:
                from dateutil import parser as date_parser
                return date_parser.parse(dt_str).date()
            except ImportError:
                pass
            except Exception:
                pass
            
            # Manual parsing: Remove microseconds that cause issues
            # Pattern: YYYY-MM-DDTHH:MM:SS.microseconds+TZ
            match = re.match(r'(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2}:\d{2})(?:\.\d+)?([\+\-Z].*)?', dt_str)
            if match:
                date_part = match.group(1)
                time_part = match.group(2)
                tz_part = match.group(3) or ''
                
                # Normalize timezone
                if tz_part == 'Z':
                    tz_part = '+00:00'
                
                # Try parsing with timezone
                try:
                    clean_str = f"{date_part}T{time_part}{tz_part}"
                    return datetime.fromisoformat(clean_str).date()
                except:
                    pass
                
                # Try without timezone
                try:
                    return datetime.strptime(date_part, '%Y-%m-%d').date()
                except:
                    pass
            
            # Last resort: extract just the date
            date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', dt_str)
            if date_match:
                year, month, day = date_match.groups()
                return datetime(int(year), int(month), int(day)).date()
                
            return None
        except Exception as e:
            print(f"Error parsing datetime '{dt_string}': {e}")
            return None
    
    try:
        # Fetch all records
        fuel_records = get_all_fuel_records()
        trip_records = list(get_all_trip_sheets())
        statutory_records = get_all_statutory_records()
        purchase_records = get_all_purchases()
        stock_issue_records = get_all_stock_issues()
        utilization_records = get_all_utilization()
        scrap_records = get_all_scrap()
        
        # Get today's date
        today = datetime.now().date()
        
        # Calculate daily data (today)
        daily_trips = [r for r in trip_records if r.get('created_at') and parse_datetime(r['created_at']) == today]
        daily_fuel = [r for r in fuel_records if r.get('created_at') and parse_datetime(r['created_at']) == today]
        daily_purchases = [r for r in purchase_records if r.get('created_at') and parse_datetime(r['created_at']) == today]
        daily_issues = [r for r in stock_issue_records if r.get('created_at') and parse_datetime(r['created_at']) == today]
        daily_utilization = [r for r in utilization_records if r.get('created_at') and parse_datetime(r['created_at']) == today]
        daily_scrap = [r for r in scrap_records if r.get('created_at') and parse_datetime(r['created_at']) == today]
        
        daily_data = {
            'total_trips': len(daily_trips),
            'total_fuel': sum(float(r.get('quantity', 0) or 0) for r in daily_fuel),
            'total_distance': sum(float(r.get('trip_distance', 0) or 0) for r in daily_trips),
            'total_students': sum(int(r.get('student_total', 0) or r.get('student_total', 0) or 0) for r in daily_trips),
            'total_faculty': sum(int(r.get('faculty_total', 0) or r.get('faculty_total', 0) or 0) for r in daily_trips),
            'total_expenditure': sum(float(r.get('amount', 0) or 0) for r in daily_fuel),
            'total_purchases': len(daily_purchases),
            'total_purchase_value': sum(float(r.get('net_payable', 0) or r.get('total_payment', 0) or 0) for r in daily_purchases),
            'total_issues': len(daily_issues),
            'total_utilization': len(daily_utilization),
            'total_scrap': len(daily_scrap),
            # quantities for stock boxes
            'purchases_qty': round(sum(float(r.get('quantity', 0) or r.get('purchased_quantity', 0) or r.get('original_quantity', 0) or 0) for r in daily_purchases), 2),
            'utilization_qty': round(sum(float(r.get('quantity', 0) or 0) for r in daily_utilization), 2),
            'scrap_qty': round(sum(float(r.get('quantity', 0) or 0) for r in daily_scrap), 2),
            # approximate opening/closing stock qty: use overall current purchase totals as closing stock
            'closing_stock_qty': round(sum(float(r.get('quantity', 0) or 0) for r in purchase_records), 2),
            'opening_stock_qty': round((sum(float(r.get('quantity', 0) or 0) for r in purchase_records) - (sum(float(r.get('quantity', 0) or r.get('purchased_quantity', 0) or r.get('original_quantity', 0) or 0) for r in daily_purchases) - sum(float(r.get('quantity', 0) or 0) for r in daily_utilization) - sum(float(r.get('quantity', 0) or 0) for r in daily_scrap))), 2),
            'fuel_labels': ['Today'],
            'fuel_values': [sum(float(r.get('quantity', 0) or 0) for r in daily_fuel)],
            'trip_labels': ['Today'],
            'trip_values': [len(daily_trips)],
            'vehicle_labels': [],
            'vehicle_values': [],
            'expenditure_values': [
                sum(float(r.get('amount', 0) or 0) for r in daily_fuel),
                0, 0, 0
            ],
            'stock_labels': ['Purchases', 'Issues', 'Utilization', 'Scrap'],
            'stock_values': [len(daily_purchases), len(daily_issues), len(daily_utilization), len(daily_scrap)],
            'days_with_entries': len(set(parse_datetime(r['created_at']).isoformat() for r in daily_trips if r.get('created_at') and parse_datetime(r['created_at'])))
        }

        # Compute statutory summary (latest record per identifier+type)
        try:
            stat_rows = statutory_records or []
            # Normalize helper for various input spellings/abbreviations
            def _normalize_type(s):
                if not s:
                    return ''
                ss = str(s).strip().lower()
                if ss in ('fc', 'fitness', 'fitness certificate', 'fitness_cert'):
                    return 'Fitness Certificate'
                if 'insur' in ss:
                    return 'Insurance'
                if ss in ('tax', 'road tax', 'road_tax', 'rate and taxes', 'rate & taxes') or 'tax' in ss:
                    return 'Road Tax'
                if ss in ('permit', 'perm', 'permit fee'):
                    return 'Permit'
                if ss in ('pucc', 'pollution', 'pollution certificate'):
                    return 'Pollution Certificate'
                if ss in ('registration', 'reg', 'regn', 'vehicle registration'):
                    return 'Registration'
                return str(s).strip().title()

            # Count all entered records by normalized type (so UI immediately reflects entries)
            per_type_counts_all = {'Fitness Certificate': 0, 'Insurance': 0, 'Road Tax': 0, 'Permit': 0, 'Pollution Certificate': 0, 'Registration': 0}
            for r in stat_rows:
                raw = (r.get('type_of_transaction') or r.get('type') or r.get('description') or '')
                n = _normalize_type(raw)
                if n in per_type_counts_all:
                    per_type_counts_all[n] += 1
            latest_by_key = {}
            for r in stat_rows:
                typ = (r.get('type_of_transaction') or r.get('type') or '').strip()
                identifier = (r.get('statutory_body_id') or r.get('vehicle_id') or r.get('registration_no') or '')
                key = f"{identifier}||{typ}".strip()
                cand_ts = r.get('created_at') or r.get('invoice_date') or r.get('date')
                if key not in latest_by_key:
                    latest_by_key[key] = (cand_ts, r)
                else:
                    prev_ts = latest_by_key[key][0]
                    try:
                        if cand_ts and prev_ts and str(cand_ts) > str(prev_ts):
                            latest_by_key[key] = (cand_ts, r)
                    except Exception:
                        pass

            compliant_count = due_soon_count = overdue_count = 0
            # prefer per-type counts from latest records but fall back to all-record counts
            per_type_counts = {'Fitness Certificate': 0, 'Insurance': 0, 'Road Tax': 0, 'Permit': 0, 'Pollution Certificate': 0, 'Registration': 0}
            # merge counts: start with counts from latest_by_key
            for _, tup in latest_by_key.items():
                rec = tup[1]
                raw = (rec.get('type_of_transaction') or rec.get('type') or '')
                n = _normalize_type(raw)
                if n in per_type_counts:
                    per_type_counts[n] += 1
            # if no latest-based counts, use all-record counts so entries show up immediately
            if sum(per_type_counts.values()) == 0:
                per_type_counts = per_type_counts_all
            today = datetime.now().date()
            # classify latest records by validity into overdue / due_soon / compliant
            for _, tup in latest_by_key.items():
                rec = tup[1]
                vd = parse_date_str(rec.get('validity_date') or rec.get('validity') or rec.get('valid_to'))
                try:
                    days_left = (vd - today).days if vd else None
                except Exception:
                    days_left = None

                if days_left is None:
                    overdue_count += 1
                elif days_left < 0:
                    overdue_count += 1
                elif days_left <= 30:
                    due_soon_count += 1
                else:
                    compliant_count += 1

                # (per-type counts already accounted for from latest_by_key merge)

        except Exception:
            compliant_count = due_soon_count = overdue_count = 0
            per_type_counts = {k: 0 for k in ('Fitness Certificate','Insurance','Road Tax','Permit','Pollution Certificate','Registration')}

        # After scanning latest records, make LIVE reflect total of per-type entries
        try:
            # LIVE = raw entered records whose validity is more than 30 days from today
            live_total = 0
            for r in stat_rows:
                try:
                    vd = parse_date_str(r.get('validity_date') or r.get('validity') or r.get('valid_to'))
                    if vd and (vd - today).days > 30:
                        live_total += 1
                except Exception:
                    continue
        except Exception:
            live_total = 0

        # Calculate weekly data (last 7 days)
        week_ago = today - timedelta(days=7)
        weekly_trips = [r for r in trip_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= week_ago]
        weekly_fuel = [r for r in fuel_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= week_ago]
        weekly_purchases = [r for r in purchase_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= week_ago]
        weekly_issues = [r for r in stock_issue_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= week_ago]
        weekly_utilization = [r for r in utilization_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= week_ago]
        weekly_scrap = [r for r in scrap_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= week_ago]
        
        # Define month_ago for monthly data
        month_ago = today - timedelta(days=30)
        
        # Group by day for weekly chart
        daily_fuel_map = defaultdict(float)
        daily_trip_map = defaultdict(int)
        for i in range(7):
            day = today - timedelta(days=i)
            daily_fuel_map[day.strftime('%a')] = 0
            daily_trip_map[day.strftime('%a')] = 0
        
        for r in weekly_fuel:
            if r.get('created_at'):
                day = parse_datetime(r['created_at'])
                if day:
                    daily_fuel_map[day.strftime('%a')] += float(r.get('quantity', 0) or 0)
        
        for r in weekly_trips:
            if r.get('created_at'):
                day = parse_datetime(r['created_at'])
                if day:
                    daily_trip_map[day.strftime('%a')] += 1
        
        weekly_data = {
            'total_trips': len(weekly_trips),
            'total_fuel': sum(float(r.get('quantity', 0) or 0) for r in weekly_fuel),
            'total_distance': sum(float(r.get('trip_distance', 0) or 0) for r in weekly_trips),
            'total_students': sum(int(r.get('student_total', 0) or r.get('student_total', 0) or 0) for r in weekly_trips),
            'total_faculty': sum(int(r.get('faculty_total', 0) or r.get('faculty_total', 0) or 0) for r in weekly_trips),
            'total_expenditure': sum(float(r.get('amount', 0) or 0) for r in weekly_fuel),
            'total_purchases': len(weekly_purchases),
            'total_purchase_value': sum(float(r.get('net_payable', 0) or r.get('total_payment', 0) or 0) for r in weekly_purchases),
            'total_issues': len(weekly_issues),
            'total_utilization': len(weekly_utilization),
            'total_scrap': len(weekly_scrap),
            'purchases_qty': round(sum(float(r.get('quantity', 0) or r.get('purchased_quantity', 0) or r.get('original_quantity', 0) or 0) for r in weekly_purchases), 2),
            'utilization_qty': round(sum(float(r.get('quantity', 0) or 0) for r in weekly_utilization), 2),
            'scrap_qty': round(sum(float(r.get('quantity', 0) or 0) for r in weekly_scrap), 2),
            'closing_stock_qty': round(sum(float(r.get('quantity', 0) or 0) for r in purchase_records), 2),
            'opening_stock_qty': round((sum(float(r.get('quantity', 0) or 0) for r in purchase_records) - (sum(float(r.get('quantity', 0) or r.get('purchased_quantity', 0) or r.get('original_quantity', 0) or 0) for r in weekly_purchases) - sum(float(r.get('quantity', 0) or 0) for r in weekly_utilization) - sum(float(r.get('quantity', 0) or 0) for r in weekly_scrap))), 2),
            'fuel_labels': list(reversed(list(daily_fuel_map.keys()))),
            'fuel_values': list(reversed(list(daily_fuel_map.values()))),
            'trip_labels': list(reversed(list(daily_trip_map.keys()))),
            'trip_values': list(reversed(list(daily_trip_map.values()))),
            'vehicle_labels': [],
            'vehicle_values': [],
            'expenditure_values': [
                sum(float(r.get('amount', 0) or 0) for r in weekly_fuel),
                0, 0, 0
            ],
            'stock_labels': ['Purchases', 'Issues', 'Utilization', 'Scrap'],
            'stock_values': [len(weekly_purchases), len(weekly_issues), len(weekly_utilization), len(weekly_scrap)],
            'days_with_entries': len(set(parse_datetime(r['created_at']).isoformat() for r in weekly_trips if r.get('created_at') and parse_datetime(r['created_at'])))
        }
        
        # Calculate monthly data (last 30 days)
        monthly_trips = [r for r in trip_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= month_ago]
        monthly_fuel = [r for r in fuel_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= month_ago]
        monthly_purchases = [r for r in purchase_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= month_ago]
        monthly_issues = [r for r in stock_issue_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= month_ago]
        monthly_utilization = [r for r in utilization_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= month_ago]
        monthly_scrap = [r for r in scrap_records if r.get('created_at') and parse_datetime(r['created_at']) and parse_datetime(r['created_at']) >= month_ago]
        
        # Group by week for monthly chart
        weekly_labels = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
        weekly_fuel_values = [0, 0, 0, 0]
        weekly_trip_values = [0, 0, 0, 0]
        
        for r in monthly_fuel:
            if r.get('created_at'):
                day = parse_datetime(r['created_at'])
                if day:
                    days_ago = (today - day).days
                    week_index = min(days_ago // 7, 3)
                    weekly_fuel_values[3 - week_index] += float(r.get('quantity', 0) or 0)
        
        for r in monthly_trips:
            if r.get('created_at'):
                day = parse_datetime(r['created_at'])
                if day:
                    days_ago = (today - day).days
                    week_index = min(days_ago // 7, 3)
                    weekly_trip_values[3 - week_index] += 1
        
        monthly_data = {
            'total_trips': len(monthly_trips),
            'total_fuel': sum(float(r.get('quantity', 0) or 0) for r in monthly_fuel),
            'total_distance': sum(float(r.get('trip_distance', 0) or 0) for r in monthly_trips),
            'total_students': sum(int(r.get('student_total', 0) or r.get('student_total', 0) or 0) for r in monthly_trips),
            'total_faculty': sum(int(r.get('faculty_total', 0) or r.get('faculty_total', 0) or 0) for r in monthly_trips),
            'total_expenditure': sum(float(r.get('amount', 0) or 0) for r in monthly_fuel),
            'total_purchases': len(monthly_purchases),
            'total_purchase_value': sum(float(r.get('net_payable', 0) or r.get('total_payment', 0) or 0) for r in monthly_purchases),
            'total_issues': len(monthly_issues),
            'total_utilization': len(monthly_utilization),
            'total_scrap': len(monthly_scrap),
            'purchases_qty': round(sum(float(r.get('quantity', 0) or r.get('purchased_quantity', 0) or r.get('original_quantity', 0) or 0) for r in monthly_purchases), 2),
            'utilization_qty': round(sum(float(r.get('quantity', 0) or 0) for r in monthly_utilization), 2),
            'scrap_qty': round(sum(float(r.get('quantity', 0) or 0) for r in monthly_scrap), 2),
            'closing_stock_qty': round(sum(float(r.get('quantity', 0) or 0) for r in purchase_records), 2),
            'opening_stock_qty': round((sum(float(r.get('quantity', 0) or 0) for r in purchase_records) - (sum(float(r.get('quantity', 0) or r.get('purchased_quantity', 0) or r.get('original_quantity', 0) or 0) for r in monthly_purchases) - sum(float(r.get('quantity', 0) or 0) for r in monthly_utilization) - sum(float(r.get('quantity', 0) or 0) for r in monthly_scrap))), 2),
            'fuel_labels': weekly_labels,
            'fuel_values': weekly_fuel_values,
            'trip_labels': weekly_labels,
            'trip_values': weekly_trip_values,
            'vehicle_labels': [],
            'vehicle_values': [],
            'expenditure_values': [
                sum(float(r.get('amount', 0) or 0) for r in monthly_fuel),
                0, 0, 0
            ],
            'stock_labels': ['Purchases', 'Issues', 'Utilization', 'Scrap'],
            'stock_values': [len(monthly_purchases), len(monthly_issues), len(monthly_utilization), len(monthly_scrap)],
            'days_with_entries': len(set(parse_datetime(r['created_at']).isoformat() for r in monthly_trips if r.get('created_at') and parse_datetime(r['created_at'])))
        }
        
        # Calculate vehicle utilization
        vehicle_usage = defaultdict(int)
        for r in trip_records:
            if r.get('vehicle_id'):
                vehicle_usage[r['vehicle_id']] += 1
        
        # All vehicles sorted by trip count (no cap - show all)
        all_vehicles_data = sorted(vehicle_usage.items(), key=lambda x: x[1], reverse=True)
        # Keep top 5 for the doughnut chart labels/values (chart gets cluttered with too many)
        chart_vehicles = all_vehicles_data[:5]
        for period_data in [daily_data, weekly_data, monthly_data]:
            period_data['vehicle_labels'] = [v[0] for v in chart_vehicles]
            period_data['vehicle_values'] = [v[1] for v in chart_vehicles]
            period_data['total_active_vehicles'] = len(all_vehicles_data)
            # Attach statutory summary counts so the dashboard shows LIVE/DueSoon/Overdue
            period_data['compliant_count'] = compliant_count
            period_data['due_soon_count'] = due_soon_count
            period_data['overdue_count'] = overdue_count
            period_data['fc_count'] = per_type_counts.get('Fitness Certificate', 0)
            period_data['insurance_count'] = per_type_counts.get('Insurance', 0)
            period_data['tax_count'] = per_type_counts.get('Road Tax', 0)
            period_data['permit_count'] = per_type_counts.get('Permit', 0)
            period_data['pucc_count'] = per_type_counts.get('Pollution Certificate', 0)
            period_data['registration_count'] = per_type_counts.get('Registration', 0)

        # Compute period-specific avg mileage from mileage_per_liter (ignore < 0.5 or > 15)
        def _avg_mpl(fuel_list):
            vals = []
            for r in fuel_list:
                mpl = r.get('mileage_per_liter')
                if mpl is not None:
                    try:
                        v = float(mpl)
                        if 0.5 <= v <= 25:
                            vals.append(v)
                    except Exception:
                        continue
            return round(sum(vals) / len(vals), 2) if vals else 0

        daily_data['avg_mileage'] = _avg_mpl(daily_fuel)
        weekly_data['avg_mileage'] = _avg_mpl(weekly_fuel)
        monthly_data['avg_mileage'] = _avg_mpl(monthly_fuel)

        # Build a map: vehicle_id -> latest valid mileage_per_liter
        # fuel_records is ordered DESC by created_at so the first matching record is the latest
        vehicle_last_mpl = {}
        for r in fuel_records:
            vid = r.get('vehicle_id')
            if not vid or vid in vehicle_last_mpl:
                continue
            mpl = r.get('mileage_per_liter')
            if mpl is not None:
                try:
                    v = float(mpl)
                    if 0.5 <= v <= 25:
                        vehicle_last_mpl[vid] = v
                except Exception:
                    pass

        # All performing vehicles (no :5 cap)
        top_vehicles = []
        for vehicle_id, trip_count in all_vehicles_data:
            vehicle_trips = [r for r in trip_records if r.get('vehicle_id') == vehicle_id]
            vehicle_fuel = [r for r in fuel_records if r.get('vehicle_id') == vehicle_id]

            total_distance = sum(float(r.get('trip_distance', 0) or 0) for r in vehicle_trips)
            total_fuel = sum(float(r.get('quantity', 0) or 0) for r in vehicle_fuel)

            # Use the last recorded mileage_per_liter for this vehicle (filtered to valid range)
            last_mpl = vehicle_last_mpl.get(vehicle_id)
            efficiency = round(last_mpl, 2) if last_mpl is not None else None

            top_vehicles.append({
                'vehicle_id': vehicle_id,
                'trips': trip_count,
                'distance': round(total_distance, 2),
                'fuel': round(total_fuel, 2),
                'efficiency': efficiency
            })
        
        # Statutory compliance
        compliant_count = 0
        due_soon_count = 0
        overdue_count = 0

        # Support multiple possible date fields that may be present in the
        # statutory records returned by different schema versions.
        for record in statutory_records:
            # Prefer explicit next_due_date, fall back to validity_date, invoice_date or date
            due_date_value = None
            for k in ('next_due_date', 'validity_date', 'invoice_date', 'date'):
                if record.get(k):
                    due_date_value = record.get(k)
                    break
            if not due_date_value:
                continue
            try:
                # Use the local parse_datetime helper where possible (handles multiple formats)
                next_due = parse_datetime(due_date_value)
                if not next_due:
                    # Last-resort: try parsing as YYYY-MM-DD
                    try:
                        next_due = datetime.strptime(str(due_date_value).split('T')[0], '%Y-%m-%d').date()
                    except Exception:
                        continue

                days_until = (next_due - today).days

                if days_until < 0:
                    overdue_count += 1
                elif days_until <= 30:
                    due_soon_count += 1
                else:
                    compliant_count += 1
            except Exception:
                # ignore parse errors for individual records
                continue
        
        # Compute active / past drivers and aggregate driver salaries from employees table
        try:
            emp_res = supabase.table('employees').select('employee_id,status,name,profile_post,basic_salary').execute()
            emp_rows = emp_res.data if emp_res.data else []
            active_drivers_count = sum(1 for e in emp_rows if str(e.get('status', '')).lower() == 'active')
            past_drivers_count = sum(1 for e in emp_rows if str(e.get('status', '')).lower() in ('inactive', 'terminated', 'resigned'))

            # Sum basic_salary for employees whose profile_post indicates they are drivers
            driver_salary_total = 0.0
            for e in emp_rows:
                try:
                    post = (e.get('profile_post') or '')
                    status = str(e.get('status', '')).lower()
                    if post and 'driver' in str(post).lower() and status == 'active':
                        v = e.get('basic_salary')
                        if v is None:
                            continue
                        driver_salary_total += float(v or 0)
                except Exception:
                    continue
        except Exception:
            active_drivers_count = 0
            past_drivers_count = 0
            driver_salary_total = 0.0

        # Expose driver counts inside the period datasets so frontend JS and PDF builder can read them
        try:
            daily_data['active_drivers'] = active_drivers_count
            weekly_data['active_drivers'] = active_drivers_count
            monthly_data['active_drivers'] = active_drivers_count
            daily_data['past_drivers'] = past_drivers_count
            weekly_data['past_drivers'] = past_drivers_count
            monthly_data['past_drivers'] = past_drivers_count
            # expose aggregated driver salaries to frontend JS
            daily_data['driver_salary'] = round(driver_salary_total, 2)
            weekly_data['driver_salary'] = round(driver_salary_total, 2)
            monthly_data['driver_salary'] = round(driver_salary_total, 2)
        except Exception:
            pass

        # Accidents / Incidents summary: count and total loss
        try:
            ai_rows = get_all_accidents_incidents() or []
            accidents_count = len(ai_rows)
            total_loss_sum = 0.0
            for r in ai_rows:
                try:
                    # prefer stored total_loss, else compute from components
                    tl = r.get('total_loss')
                    if tl is None:
                        treat = float(r.get('treatment_expenditure') or 0)
                        pol = float(r.get('police_total_paid') or 0)
                        sett = float(r.get('settlement_amount') or 0)
                        tl = treat + pol + sett
                    total_loss_sum += float(tl or 0)
                except Exception:
                    continue
            # attach to period datasets for frontend use
            # Backwards-compatible keys for frontend: support both "accidents_*" and
            # "incidents_*" naming used in different places of the JS/template.
            daily_data['accidents_count'] = accidents_count
            weekly_data['accidents_count'] = accidents_count
            monthly_data['accidents_count'] = accidents_count
            daily_data['accidents_total_loss'] = round(total_loss_sum, 2)
            weekly_data['accidents_total_loss'] = round(total_loss_sum, 2)
            monthly_data['accidents_total_loss'] = round(total_loss_sum, 2)

            # Also expose `incidents_*` keys expected by the dashboard JS
            daily_data['incidents_count'] = accidents_count
            weekly_data['incidents_count'] = accidents_count
            monthly_data['incidents_count'] = accidents_count
            daily_data['incidents_payments_total'] = round(total_loss_sum, 2)
            weekly_data['incidents_payments_total'] = round(total_loss_sum, 2)
            monthly_data['incidents_payments_total'] = round(total_loss_sum, 2)
        except Exception:
            accidents_count = 0
            total_loss_sum = 0.0

        # compute today's statutory payments (for Rate & Taxes / Payments Made)
        try:
            rate_and_taxes_today = round(sum(float(r.get('total_amount', 0) or r.get('amount', 0) or 0) for r in statutory_records if r.get('created_at') and parse_datetime(r['created_at']) == today), 2)
        except Exception:
            rate_and_taxes_today = 0.0

        # attach today's statutory payments into the period datasets for JS
        try:
            daily_data['rate_and_taxes'] = rate_and_taxes_today
            weekly_data['rate_and_taxes'] = rate_and_taxes_today
            monthly_data['rate_and_taxes'] = rate_and_taxes_today
        except Exception:
            pass

        # log per-type counts for debugging why LIVE may be zero
        try:
            app.logger.info(f"Statutory records: total={len(stat_rows)}, per_type_counts={per_type_counts}, per_type_counts_all={per_type_counts_all}, live_total={live_total}, rate_and_taxes_today={rate_and_taxes_today}")
        except Exception:
            pass

        # pass per-type counts so initial server-rendered boxes show values
        # attach overall stock totals so dashboard and inventory show the same authoritative values
        try:
            overall_stock_totals = get_stock_totals()
        except Exception:
            overall_stock_totals = {}

        # Compute monthly Opening and Closing from Jan 2026 through current month.
        try:
            from datetime import date, timedelta
            monthly_opening_stocks = []
            months = []
            # start from Jan 2026
            start_year = 2026
            start_month = 1
            # build months list from Jan 2026 to current month (inclusive)
            y = start_year
            m = start_month
            while (y < today.year) or (y == today.year and m <= today.month):
                ms = date(y, m, 1)
                if m == 12:
                    next_ms = date(y + 1, 1, 1)
                else:
                    next_ms = date(y, m + 1, 1)
                me = next_ms - timedelta(days=1)
                months.append((ms, me))
                # increment month
                m += 1
                if m > 12:
                    m = 1
                    y += 1

            def _sum_between(records, field_names, start_dt, end_dt):
                s = 0.0
                for r in (records or []):
                    try:
                        cd = r.get('created_at') or r.get('date') or r.get('invoice_date')
                        rd = parse_datetime(cd)
                        if not rd:
                            continue
                        if rd >= start_dt and rd <= end_dt:
                            # Use FIRST non-None field only (avoid double-counting multi-field records)
                            for fn in field_names:
                                val = r.get(fn)
                                if val is None:
                                    continue
                                try:
                                    v = float(val or 0)
                                    s += v
                                    break  # stop at first valid field
                                except Exception:
                                    try:
                                        v = float(str(val).replace(',', ''))
                                        s += v
                                        break
                                    except Exception:
                                        continue
                    except Exception:
                        continue
                return s

            def _sum_before(records, field_names, upto_date):
                s = 0.0
                for r in (records or []):
                    try:
                        cd = r.get('created_at') or r.get('date') or r.get('invoice_date')
                        rd = parse_datetime(cd)
                        if not rd:
                            continue
                        if rd < upto_date:
                            # Use FIRST non-None field only (avoid double-counting multi-field records)
                            for fn in field_names:
                                val = r.get(fn)
                                if val is None:
                                    continue
                                try:
                                    v = float(val or 0)
                                    s += v
                                    break  # stop at first valid field
                                except Exception:
                                    try:
                                        v = float(str(val).replace(',', ''))
                                        s += v
                                        break
                                    except Exception:
                                        continue
                    except Exception:
                        continue
                return s

            # For first month opening: total purchases before first month (per request)
            prev_closing = 0.0
            if months:
                first_ms = months[0][0]
                purchases_before = _sum_before(purchase_records, ['quantity', 'purchased_quantity', 'original_quantity'], first_ms)
                utilization_before = _sum_before(utilization_records, ['quantity'], first_ms)
                scrap_before = _sum_before(scrap_records, ['quantity'], first_ms)
                issues_before = _sum_before(stock_issue_records, ['quantity_issued', 'quantity'], first_ms)
                # Opening shown for first month should be total purchases before it (user requested)
                opening_first = purchases_before
                # compute prev_closing as net before first month for continuity
                prev_closing = round(purchases_before - utilization_before - scrap_before - issues_before, 2)
            
            for idx, (ms, me) in enumerate(months):
                if idx == 0:
                    opening_qty = opening_first
                else:
                    opening_qty = prev_closing

                # sums within the month
                purchases_in = _sum_between(purchase_records, ['quantity', 'purchased_quantity', 'original_quantity'], ms, me)
                utilization_in = _sum_between(utilization_records, ['quantity'], ms, me)
                scrap_in = _sum_between(scrap_records, ['quantity'], ms, me)
                issues_in = _sum_between(stock_issue_records, ['quantity_issued', 'quantity'], ms, me)

                closing_qty = opening_qty + purchases_in - utilization_in - scrap_in - issues_in
                closing_qty = round(closing_qty, 2)

                # For the current month, override closing with the authoritative DB value
                # (overall_stock_totals.total_current_qty) so monthly table matches inventory page.
                is_current_month = (ms.year == today.year and ms.month == today.month)
                if is_current_month and isinstance(overall_stock_totals, dict):
                    db_current_qty = overall_stock_totals.get('total_current_qty')
                    if db_current_qty is not None:
                        closing_qty = round(float(db_current_qty), 2)

                monthly_opening_stocks.append({'label': ms.strftime('%b %Y'), 'opening': round(opening_qty, 2), 'closing': closing_qty})

                # set prev_closing for next month
                prev_closing = closing_qty
            # Debug: log details for March 2026 if present
            try:
                for entry in monthly_opening_stocks:
                    if entry.get('label') == 'Mar 2026':
                        app.logger.info(f"[DEBUG] Mar 2026 -> opening={entry.get('opening')} closing={entry.get('closing')}")
                        # Also log detailed month sums to aid debugging
                        # find ms, me for Mar 2026
                        for ms, me in months:
                            if ms.strftime('%b %Y') == 'Mar 2026':
                                p_in = _sum_between(purchase_records, ['quantity', 'purchased_quantity', 'original_quantity'], ms, me)
                                u_in = _sum_between(utilization_records, ['quantity'], ms, me)
                                s_in = _sum_between(scrap_records, ['quantity'], ms, me)
                                i_in = _sum_between(stock_issue_records, ['quantity_issued', 'quantity'], ms, me)
                                app.logger.info(f"[DEBUGDETAIL] Mar2026 sums: purchases_in={p_in} utilization_in={u_in} scrap_in={s_in} issues_in={i_in}")
                                break
            except Exception:
                pass
        except Exception:
            monthly_opening_stocks = []

        # Determine current opening stock (opening for the most recent month)
        try:
            if monthly_opening_stocks and len(monthly_opening_stocks) > 0:
                opening_stock_current = monthly_opening_stocks[-1].get('opening', 0.0)
            else:
                opening_stock_current = overall_stock_totals.get('total_current_qty', 0.0) if isinstance(overall_stock_totals, dict) else 0.0
        except Exception:
            opening_stock_current = 0.0

        return render_template('admin_analytics_dashboard.html',
                             daily_data=daily_data,
                             weekly_data=weekly_data,
                             monthly_data=monthly_data,
                             total_trips=daily_data['total_trips'],
                             total_fuel=round(daily_data['total_fuel'], 2),
                             total_distance=round(daily_data['total_distance'], 2),
                             total_expenditure=round(daily_data['total_expenditure'], 2),
                             total_purchases=daily_data['total_purchases'],
                             total_purchase_value=round(daily_data['total_purchase_value'], 2),
                             total_issues=daily_data['total_issues'],
                             total_utilization=daily_data['total_utilization'],
                             total_scrap=daily_data['total_scrap'],
                             total_active_vehicles=len(all_vehicles_data),
                             top_vehicles=top_vehicles,
                            active_drivers=active_drivers_count,
                            past_drivers=past_drivers_count,
                            compliant_count=live_total,
                            due_soon_count=due_soon_count,
                            overdue_count=overdue_count,
                            fc_count=per_type_counts_all.get('Fitness Certificate', 0),
                            insurance_count=per_type_counts_all.get('Insurance', 0),
                            tax_count=per_type_counts_all.get('Road Tax', 0),
                            permit_count=per_type_counts_all.get('Permit', 0),
                            pucc_count=per_type_counts_all.get('Pollution Certificate', 0),
                            registration_count=per_type_counts_all.get('Registration', 0),
                            driver_salary=round(driver_salary_total, 2),
                            rate_and_taxes=rate_and_taxes_today,
                            overall_stock_totals=overall_stock_totals,
                            opening_stock_monthly=monthly_opening_stocks,
                            opening_stock=opening_stock_current,
                            opening_stock_qty=opening_stock_current)
                            
    
    except Exception as e:
        print(f"Error in analytics dashboard: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading analytics: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))


@app.route('/api/statutory-records')
@admin_required
def api_statutory_records():
    """Return statutory records filtered by status query param.
    Query param `status` accepts: `compliant`, `due_soon`, `overdue`, or `all`.
    """
    status_filter = (request.args.get('status') or 'all').strip().lower()
    try:
        statutory_records = get_all_statutory_records() or []
    except Exception:
        statutory_records = []

    # Also include vehicle-level validity fields (from vehicle page) so the
    # API reflects compliance coming from both statutory entries and vehicle records.
    try:
        vehicle_rows = get_all_vehicles() or []
    except Exception:
        vehicle_rows = []
    veh_stat_rows = []
    for v in vehicle_rows:
        vid = v.get('vehicle_id') or v.get('id') or ''
        reg = v.get('registration_no') or v.get('registration') or ''
        for field_key, label in VEHICLE_DATE_FIELDS.items():
            if v.get(field_key):
                veh_stat_rows.append({
                    'type_of_transaction': label,
                    'vehicle_id': vid,
                    'registration_no': reg,
                    'validity_date': v.get(field_key),
                    'source': 'vehicle_record'
                })
    statutory_records = (statutory_records or []) + veh_stat_rows

    today = datetime.now().date()
    out = []
    for record in statutory_records:
        # pick possible due-date fields in preference order
        due_date_value = None
        for k in ('next_due_date', 'validity_date', 'invoice_date', 'date'):
            if record.get(k):
                due_date_value = record.get(k)
                break

        parsed = parse_date_str(due_date_value)
        days_until = None
        status_label = 'unknown'
        due_iso = None
        if parsed:
            days_until = (parsed - today).days
            due_iso = parsed.isoformat()
            if days_until < 0:
                status_label = 'overdue'
            elif days_until <= 30:
                status_label = 'due_soon'
            else:
                status_label = 'compliant'

        if status_filter != 'all' and status_filter != status_label:
            continue

        # sanitize values for JSON (dates -> isoformat strings)
        def _clean(v):
            try:
                if v is None:
                    return None
                if isinstance(v, (str, int, float, bool, list, dict)):
                    return v
                if hasattr(v, 'isoformat'):
                    try:
                        return v.isoformat()
                    except Exception:
                        return str(v)
                return str(v)
            except Exception:
                return str(v)

        cleaned = {}
        if isinstance(record, dict):
            for k, v in record.items():
                cleaned[k] = _clean(v)
        else:
            # fallback: try to convert to dict-like
            try:
                cleaned = dict(record)
            except Exception:
                cleaned = {'record': str(record)}

        cleaned['statutory_status'] = status_label
        cleaned['days_until'] = days_until
        cleaned['due_date'] = due_iso
        out.append(cleaned)

    return jsonify({'success': True, 'records': out}), 200


@app.route('/api/analytics-custom')
@admin_required
def api_analytics_custom():
    """Return analytics data JSON for a custom date range."""
    from datetime import datetime
    from collections import defaultdict
    import re

    start_str = request.args.get('start')
    end_str = request.args.get('end')
    if not start_str or not end_str:
        return jsonify({'error': 'start and end required'}), 400

    # Accept flexible date formats (YYYY-MM-DD, DD-MM-YYYY, ISO timestamps, etc.)
    try:
        # Prefer the app-level helper `parse_date_str` if available in this module
        try:
            start_date = parse_date_str(start_str)
            end_date = parse_date_str(end_str)
        except Exception:
            start_date = None
            end_date = None

        # Fallback: try common formats
        if not start_date:
            # Try common dash-separated formats first
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except Exception:
                try:
                    start_date = datetime.strptime(start_str, '%d-%m-%Y').date()
                except Exception:
                    # Try slash-separated formats like DD/MM/YYYY or YYYY/MM/DD
                    try:
                        start_date = datetime.strptime(start_str, '%d/%m/%Y').date()
                    except Exception:
                        try:
                            start_date = datetime.strptime(start_str, '%Y/%m/%d').date()
                        except Exception:
                            # last resort: extract a date-like substring and normalize separators
                            m = re.search(r'(\d{4}[\-/]\d{2}[\-/]\d{2}|\d{2}[\-/]\d{2}[\-/]\d{4})', str(start_str))
                            if m:
                                s = m.group(1).replace('/', '-')
                                # If it's DD-MM-YYYY convert to YYYY-MM-DD
                                if re.match(r'\d{2}-\d{2}-\d{4}', s):
                                    parts = s.split('-')
                                    s = parts[2] + '-' + parts[1] + '-' + parts[0]
                                try:
                                    start_date = datetime.strptime(s, '%Y-%m-%d').date()
                                except Exception:
                                    start_date = None

        if not end_date:
            try:
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            except Exception:
                try:
                    end_date = datetime.strptime(end_str, '%d-%m-%Y').date()
                except Exception:
                    try:
                        end_date = datetime.strptime(end_str, '%d/%m/%Y').date()
                    except Exception:
                        try:
                            end_date = datetime.strptime(end_str, '%Y/%m/%d').date()
                        except Exception:
                            m2 = re.search(r'(\d{4}[\-/]\d{2}[\-/]\d{2}|\d{2}[\-/]\d{2}[\-/]\d{4})', str(end_str))
                            if m2:
                                s2 = m2.group(1).replace('/', '-')
                                if re.match(r'\d{2}-\d{2}-\d{4}', s2):
                                    p = s2.split('-')
                                    s2 = p[2] + '-' + p[1] + '-' + p[0]
                                try:
                                    end_date = datetime.strptime(s2, '%Y-%m-%d').date()
                                except Exception:
                                    end_date = None

        if not start_date or not end_date:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD or DD-MM-YYYY'}), 400
    except Exception as exc:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD', 'detail': str(exc)}), 400

    def to_date(val):
        if not val:
            return None
        try:
            s = str(val).strip()
            m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
            if m:
                return datetime.strptime(m.group(1), '%Y-%m-%d').date()
        except Exception:
            pass
        return None

    fuel_records = get_all_fuel_records()
    trip_records = list(get_all_trip_sheets())
    purchase_records = get_all_purchases()
    stock_issue_records = get_all_stock_issues()
    utilization_records = get_all_utilization()
    scrap_records = get_all_scrap()

    def row_date(r):
        # Try several common date fields on records and parse them to date
        for key in ('date_time', 'created_at', 'date', 'trip_date', 'createdAt'):
            v = r.get(key)
            if not v:
                continue
            try:
                # Prefer module-level parse_date_str for varied formats
                d = parse_date_str(v)
                if d:
                    return d
            except Exception:
                pass
            # Fallback to simple YYYY-MM-DD extraction
            try:
                m = re.search(r'(\d{4}-\d{2}-\d{2})', str(v))
                if m:
                    return datetime.strptime(m.group(1), '%Y-%m-%d').date()
            except Exception:
                pass
        return None

    def in_range(r):
        d = row_date(r)
        return d and start_date <= d <= end_date

    f = [r for r in fuel_records if in_range(r)]
    t = [r for r in trip_records if in_range(r)]
    p = [r for r in purchase_records if in_range(r)]
    si = [r for r in stock_issue_records if in_range(r)]
    u = [r for r in utilization_records if in_range(r)]
    sc = [r for r in scrap_records if in_range(r)]

    # Build day-by-day labels
    from datetime import timedelta
    days = []
    cur = start_date
    while cur <= end_date:
        days.append(cur)
        cur += timedelta(days=1)

    fuel_by_day = defaultdict(float)
    trip_by_day = defaultdict(int)
    for r in f:
        d = row_date(r)
        if d:
            fuel_by_day[d.strftime('%d/%m')] += float(r.get('quantity', 0) or 0)
    for r in t:
        d = row_date(r)
        if d:
            trip_by_day[d.strftime('%d/%m')] += 1

    labels = [d.strftime('%d/%m') for d in days]

    vehicle_usage = defaultdict(int)
    for r in t:
        if r.get('vehicle_id'):
            vehicle_usage[r['vehicle_id']] += 1
    all_v = sorted(vehicle_usage.items(), key=lambda x: x[1], reverse=True)
    top5 = all_v[:5]

    data = {
        'total_trips': len(t),
        'total_fuel': round(sum(float(r.get('quantity', 0) or 0) for r in f), 2),
        'total_distance': round(sum(float(r.get('trip_distance', 0) or 0) for r in t), 2),
        'total_expenditure': round(sum(float(r.get('amount', 0) or 0) for r in f), 2),
        'total_purchases': len(p),
        'total_purchase_value': round(sum(float(r.get('net_payable', 0) or r.get('total_payment', 0) or 0) for r in p), 2),
        'total_issues': len(si),
        'total_utilization': len(u),
        'total_scrap': len(sc),
        'total_active_vehicles': len(all_v),
        'fuel_labels': labels,
        'fuel_values': [fuel_by_day.get(d.strftime('%d/%m'), 0) for d in days],
        'trip_labels': labels,
        'trip_values': [trip_by_day.get(d.strftime('%d/%m'), 0) for d in days],
        'vehicle_labels': [v[0] for v in top5],
        'vehicle_values': [v[1] for v in top5],
        'expenditure_values': [
            round(sum(float(r.get('amount', 0) or 0) for r in f), 2),
            0, 0, 0
        ],
        'stock_labels': ['Purchases', 'Issues', 'Utilization', 'Scrap'],
        'stock_values': [len(p), len(si), len(u), len(sc)]
    }
    # Average mileage for the custom range (mileage_per_liter, ignore < 0.5 or > 15)
    _mpl_custom = []
    for r in f:
        mpl = r.get('mileage_per_liter')
        if mpl is not None:
            try:
                v = float(mpl)
                if 0.5 <= v <= 15:
                    _mpl_custom.append(v)
            except Exception:
                pass
    data['avg_mileage'] = round(sum(_mpl_custom) / len(_mpl_custom), 2) if _mpl_custom else 0
    # Quantities for stock metrics (make opening/closing authoritative by using
    # cumulative records up to the date boundaries rather than mixing filtered
    # and unfiltered snapshots).
    purchases_qty = round(sum(float(r.get('quantity', 0) or r.get('purchased_quantity', 0) or r.get('original_quantity', 0) or 0) for r in p), 2)
    utilization_qty = round(sum(float(r.get('quantity', 0) or 0) for r in u), 2)
    scrap_qty = round(sum(float(r.get('quantity', 0) or 0) for r in sc), 2)

    # Helper to safely parse created_at to date using the local `to_date` helper
    # Build cumulative sets up to end_date and up to (start_date - 1)
    from datetime import timedelta
    end_cutoff = end_date
    start_before = start_date - timedelta(days=1)

    def _sum_qty_up_to(rows, date_field='created_at', cutoff=end_cutoff):
        s = 0.0
        for r in rows:
            d = to_date(r.get(date_field))
            if d and d <= cutoff:
                try:
                    s += float(r.get('quantity', 0) or r.get('purchased_quantity', 0) or r.get('original_quantity', 0) or 0)
                except Exception:
                    try:
                        s += float(str(r.get('quantity', 0)).replace(',', ''))
                    except Exception:
                        pass
        return s

    # cumulative up to end_date
    purchases_upto_end = round(_sum_qty_up_to(purchase_records, cutoff=end_cutoff), 2)
    utilization_upto_end = round(_sum_qty_up_to(utilization_records, cutoff=end_cutoff), 2)
    scrap_upto_end = round(_sum_qty_up_to(scrap_records, cutoff=end_cutoff), 2)
    # issued quantities may be stored under different keys
    total_issued_upto_end = 0.0
    for r in stock_issue_records:
        d = to_date(r.get('created_at'))
        if d and d <= end_cutoff:
            try:
                total_issued_upto_end += float(r.get('quantity_issued') or r.get('quantity') or 0)
            except Exception:
                try:
                    total_issued_upto_end += float(str(r.get('quantity', 0)).replace(',', ''))
                except Exception:
                    pass

    # cumulative up to the day before start_date (opening snapshot)
    purchases_before = round(_sum_qty_up_to(purchase_records, cutoff=start_before), 2)
    utilization_before = round(_sum_qty_up_to(utilization_records, cutoff=start_before), 2)
    scrap_before = round(_sum_qty_up_to(scrap_records, cutoff=start_before), 2)
    total_issued_before = 0.0
    for r in stock_issue_records:
        d = to_date(r.get('created_at'))
        if d and d <= start_before:
            try:
                total_issued_before += float(r.get('quantity_issued') or r.get('quantity') or 0)
            except Exception:
                try:
                    total_issued_before += float(str(r.get('quantity', 0)).replace(',', ''))
                except Exception:
                    pass

    # closing = purchases up to end - removals up to end
    closing_stock_qty = round(max(0.0, purchases_upto_end - utilization_upto_end - scrap_upto_end - total_issued_upto_end), 2)
    # opening = purchases up to before-start - removals up to before-start
    opening_stock_qty = round(max(0.0, purchases_before - utilization_before - scrap_before - total_issued_before), 2)

    data['purchases_qty'] = purchases_qty
    data['utilization_qty'] = utilization_qty
    data['scrap_qty'] = scrap_qty
    data['closing_stock_qty'] = closing_stock_qty
    data['opening_stock_qty'] = opening_stock_qty
    # Compute monetary totals for stock management boxes: purchases, utilization, issues, scrap
    try:
        # Build cost per unit map from all purchase_records (use net_payable/quantity when available)
        cost_per_unit = {}
        for item in purchase_records:
            raw_part = item.get('part_number') or item.get('part_no') or item.get('part') or ''
            if not raw_part:
                continue
            key = str(raw_part).strip().lower()
            try:
                qty = float(item.get('quantity', 0) or item.get('original_quantity', 0) or item.get('purchased_quantity', 0) or 0)
            except Exception:
                qty = 0
            try:
                net = float(item.get('net_payable', 0) or item.get('total_payment', 0) or item.get('total_value', 0) or 0)
            except Exception:
                net = 0

            rate = 0.0
            if qty > 0:
                rate = net / qty
            else:
                try:
                    rate = float(item.get('rate') or 0)
                except Exception:
                    rate = 0.0

            if key in cost_per_unit:
                # average to smooth multiple purchases
                cost_per_unit[key] = (cost_per_unit[key] + rate) / 2.0
            else:
                cost_per_unit[key] = rate

        # Sum monetary values for utilization, scrap and issues within the date range
        util_amount = 0.0
        for r in u:
            raw_part = r.get('part_no') or r.get('part_number') or ''
            if not raw_part:
                continue
            key = str(raw_part).strip().lower()
            try:
                q = float(r.get('quantity', 0) or 0)
            except Exception:
                q = 0
            util_amount += q * float(cost_per_unit.get(key, 0))

        scrap_amount = 0.0
        for r in sc:
            raw_part = r.get('part_no') or r.get('part_number') or ''
            if not raw_part:
                continue
            key = str(raw_part).strip().lower()
            try:
                q = float(r.get('quantity', 0) or 0)
            except Exception:
                q = 0
            scrap_amount += q * float(cost_per_unit.get(key, 0))

        issue_amount = 0.0
        for r in si:
            raw_part = r.get('part_no') or r.get('part_number') or ''
            if not raw_part:
                continue
            key = str(raw_part).strip().lower()
            try:
                q = float(r.get('quantity_issued', 0) or r.get('quantity', 0) or 0)
            except Exception:
                q = 0
            issue_amount += q * float(cost_per_unit.get(key, 0))

        # Expose monetary totals (purchase_expenditure kept for compatibility)
        data['purchase_expenditure'] = data.get('total_purchase_value', 0)
        data['utilization_expenditure'] = round(util_amount, 2)
        data['scrap_expenditure'] = round(scrap_amount, 2)
        data['issue_expenditure'] = round(issue_amount, 2)
    except Exception:
        data['purchase_expenditure'] = data.get('total_purchase_value', 0)
        data['utilization_expenditure'] = 0
        data['scrap_expenditure'] = 0
        data['issue_expenditure'] = 0
    # Compute student/faculty/guest/passenger totals for the custom range
    def safe_int(val):
        try:
            return int(val or 0)
        except Exception:
            try:
                return int(float(str(val).replace(',', '').strip()))
            except Exception:
                return 0

    total_students = 0
    total_faculty = 0
    total_guests = 0
    total_passengers = 0
    for r in t:
        s = safe_int(r.get('student_total'))
        if not s:
            s = safe_int(r.get('student_male')) + safe_int(r.get('student_female')) + safe_int(r.get('student_transgender'))
        total_students += s

        fct = safe_int(r.get('faculty_total'))
        if not fct:
            fct = safe_int(r.get('faculty_male')) + safe_int(r.get('faculty_female')) + safe_int(r.get('faculty_transgender'))
        total_faculty += fct

        g = safe_int(r.get('guest_total'))
        if not g:
            g = safe_int(r.get('guest_male')) + safe_int(r.get('guest_female')) + safe_int(r.get('guest_transgender'))
        total_guests += g

        p = safe_int(r.get('cumulative_strength') or r.get('total_strength'))
        if not p:
            p = safe_int(r.get('male_count')) + safe_int(r.get('female_count')) + safe_int(r.get('transgender_count'))
        total_passengers += p

    data['total_students'] = total_students
    data['total_faculty'] = total_faculty
    data['total_guests'] = total_guests
    data['total_passengers'] = total_passengers
    # days with trip entries in the custom range
    data['days_with_entries'] = len(set(row_date(r).isoformat() for r in t if row_date(r)))
    # include active/past drivers counts from employees table
    try:
        emp_res = supabase.table('employees').select('status').execute()
        emp_rows = emp_res.data if emp_res.data else []
        data['active_drivers'] = sum(1 for e in emp_rows if str(e.get('status','')).lower() == 'active')
        data['past_drivers'] = sum(1 for e in emp_rows if str(e.get('status','')).lower() in ('inactive','terminated','resigned'))
    except Exception:
        data['active_drivers'] = 0
        data['past_drivers'] = 0

    # Accidents / Incidents: count and total loss within the requested range
    try:
        ai_rows = get_all_accidents_incidents() or []
        def ai_in_range(r):
            d = to_date(r.get('created_at') or r.get('date_time') or r.get('date'))
            return d and start_date <= d <= end_date

        ai_filtered = [r for r in ai_rows if ai_in_range(r)]
        incidents_count = len(ai_filtered)
        incidents_total = 0.0
        for r in ai_filtered:
            try:
                tl = r.get('total_loss')
                if tl is None:
                    treat = float(r.get('treatment_expenditure') or 0)
                    pol = float(r.get('police_total_paid') or 0)
                    sett = float(r.get('settlement_amount') or 0)
                    tl = treat + pol + sett
                incidents_total += float(tl or 0)
            except Exception:
                continue

        data['incidents_count'] = incidents_count
        data['incidents_payments_total'] = round(incidents_total, 2)
        # Backwards-compatible keys
        data['accidents_count'] = incidents_count
        data['accidents_total_loss'] = round(incidents_total, 2)
    except Exception:
        data['incidents_count'] = 0
        data['incidents_payments_total'] = 0
        data['accidents_count'] = 0
        data['accidents_total_loss'] = 0

    # Statutory counts: compute latest validity per vehicle/statutory type and classify
    try:
        stat_rows = get_all_statutory_records() or []
        # Group by identifier + type to pick latest record
        latest_by_key = {}
        from datetime import date as _date
        # Also compute raw counts of all entered records by normalized type
        per_type_counts_all = {'Fitness Certificate': 0, 'Insurance': 0, 'Road Tax': 0, 'Permit': 0, 'Pollution Certificate': 0, 'Registration': 0}
        for r in stat_rows:
            typ = (r.get('type_of_transaction') or r.get('type') or '').strip()
            identifier = (r.get('statutory_body_id') or r.get('vehicle_id') or r.get('registration_no') or '')
            key = f"{identifier}||{typ}".strip()
            # prefer created_at or invoice_date for recency
            cand_ts = r.get('created_at') or r.get('invoice_date') or r.get('date')
            if key not in latest_by_key:
                latest_by_key[key] = (cand_ts, r)
            else:
                prev_ts = latest_by_key[key][0]
                try:
                    # string compare is okay for ISO dates; fallback to keeping existing
                    if cand_ts and prev_ts and str(cand_ts) > str(prev_ts):
                        latest_by_key[key] = (cand_ts, r)
                except Exception:
                    pass
            # count normalized raw type for overall LIVE calculation
            try:
                n = normalize_typename(typ)
                if n in per_type_counts_all:
                    per_type_counts_all[n] += 1
            except Exception:
                pass

        compliant_count = 0
        due_soon_count = 0
        overdue_count = 0
        per_type_counts = {'Fitness Certificate': 0, 'Insurance': 0, 'Road Tax': 0, 'Permit': 0, 'Pollution Certificate': 0, 'Registration': 0}
        # helper to normalize type strings and accept common abbreviations
        def normalize_typename(s):
            if not s:
                return ''
            ss = str(s).strip().lower()
            if ss in ('fc', 'fitness', 'fitness certificate', 'fitness_cert'):
                return 'Fitness Certificate'
            if 'insur' in ss:
                return 'Insurance'
            if ss in ('tax', 'road tax', 'road_tax', 'rate and taxes', 'rate & taxes') or 'tax' in ss:
                return 'Road Tax'
            if ss in ('permit', 'perm', 'permit fee'):
                return 'Permit'
            if ss in ('pucc', 'pollution', 'pollution certificate', 'pollution certificate (pucc)'):
                return 'Pollution Certificate'
            if ss in ('registration', 'reg', 'regn', 'vehicle registration'):
                return 'Registration'
            # fallback: title-case the string
            return str(s).strip().title()
        today = _date.today()
        for _, tup in latest_by_key.items():
            rec = tup[1]
            vd = None
            try:
                vd = parse_date_str(rec.get('validity_date') or rec.get('validity') or rec.get('valid_to'))
            except Exception:
                vd = None
            try:
                if vd:
                    days_left = (vd - today).days
                else:
                    days_left = None
            except Exception:
                days_left = None

            if days_left is None:
                # unknown validity: do not count as compliant; treat as needs attention (count as overdue)
                overdue_count += 1
            else:
                if days_left < 0:
                    overdue_count += 1
                elif days_left <= 30:
                    due_soon_count += 1
                    compliant_count += 1
                else:
                    compliant_count += 1

            typname_raw = (rec.get('type_of_transaction') or rec.get('type') or '')
            typname = normalize_typename(typname_raw)
            # Count per-type entries regardless of validity so the dashboard reflects entered records
            if typname in per_type_counts:
                per_type_counts[typname] += 1
            else:
                # if it's a new/unknown type, add to map to avoid losing it (but do not crash)
                per_type_counts.setdefault(typname, 0)
                per_type_counts[typname] += 1
        # Also aggregate statutory payments within the requested date range (map to payments.rate_and_taxes)
        try:
            stat_in_range = [r for r in stat_rows if to_date(r.get('created_at')) and start_date <= to_date(r.get('created_at')) <= end_date]
            payment_rate_and_taxes = round(sum(float(r.get('total_amount', 0) or r.get('amount', 0) or 0) for r in stat_in_range), 2)
        except Exception:
            payment_rate_and_taxes = 0.0
        # Also compute driver salary aggregate (sum basic_salary for active drivers)
        try:
            emp_res = supabase.table('employees').select('profile_post,status,basic_salary').execute()
            emp_rows = emp_res.data if emp_res.data else []
            driver_salary_total = 0.0
            for e in emp_rows:
                try:
                    post = (e.get('profile_post') or '')
                    status = str(e.get('status', '')).lower()
                    if post and 'driver' in str(post).lower() and status == 'active':
                        v = e.get('basic_salary')
                        if v is None:
                            continue
                        driver_salary_total += float(v or 0)
                except Exception:
                    continue
        except Exception:
            driver_salary_total = 0.0
        # LIVE should reflect all entered records (not deduped by vehicle+type)
        try:
            # LIVE = count of entered records whose validity is more than 30 days from today
            live_all = 0
            for r in stat_rows:
                vd = parse_date_str(r.get('validity_date') or r.get('validity') or r.get('valid_to'))
                try:
                    if vd and (vd - today).days > 30:
                        live_all += 1
                except Exception:
                    continue
        except Exception:
            live_all = compliant_count
        data['compliant_count'] = live_all
        data['due_soon_count'] = due_soon_count
        data['overdue_count'] = overdue_count
        # expose per-type counts using keys used in template
        data['fc_count'] = per_type_counts_all.get('Fitness Certificate', 0)
        data['insurance_count'] = per_type_counts_all.get('Insurance', 0)
        data['tax_count'] = per_type_counts_all.get('Road Tax', 0)
        data['permit_count'] = per_type_counts_all.get('Permit', 0)
        data['pucc_count'] = per_type_counts_all.get('Pollution Certificate', 0)
        data['registration_count'] = per_type_counts_all.get('Registration', 0)
        # payments mapping used by the dashboard (Payments Made -> Rate & Taxes)
        data['payments'] = data.get('payments', {})
        data['payments']['rate_and_taxes'] = payment_rate_and_taxes
        # Expose top-level rate_and_taxes and driver_salary for frontend compatibility
        data['rate_and_taxes'] = payment_rate_and_taxes
        data['driver_salary'] = round(driver_salary_total, 2)
    except Exception:
        data['compliant_count'] = 0
        data['due_soon_count'] = 0
        data['overdue_count'] = 0
        data['fc_count'] = 0
        data['insurance_count'] = 0
        data['tax_count'] = 0
        data['permit_count'] = 0
        data['pucc_count'] = 0
        data['registration_count'] = 0
    return jsonify(data)


# =====================================================
# ADMIN USER MANAGEMENT ROUTES
# =====================================================

@app.route('/admin/users', methods=['GET'])
@admin_required
def admin_users():
    try:
        users = get_all_users() or []
    except Exception:
        users = []
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/add', methods=['GET', 'POST'])
@admin_required
def admin_add_user():
    if request.method == 'POST':
        user_data = {
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'full_name': request.form.get('full_name'),
            'phone': request.form.get('phone') or None,
            'department': request.form.get('department') or None,
            'role': request.form.get('role', 'user'),
            'is_active': request.form.get('is_active', 'true') == 'true'
        }
        try:
            created = admin_create_user(user_data)
            if created:
                flash('User created successfully!', 'success')
                return redirect(url_for('admin_users'))
            else:
                flash('Failed to create user.', 'danger')
        except Exception as e:
            flash('Error creating user: ' + str(e), 'danger')

    return render_template('admin_add_user.html')


@app.route('/admin/users/edit/<user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    if request.method == 'POST':
        user_data = {
            'email': request.form.get('email'),
            'full_name': request.form.get('full_name'),
            'phone': request.form.get('phone') or None,
            'department': request.form.get('department') or None,
            'role': request.form.get('role', 'user'),
            'is_active': request.form.get('is_active') == 'true'
        }
        
        # Only update password if provided
        new_password = request.form.get('password')
        if new_password:
            user_data['password'] = new_password
        
        result = admin_update_user(user_id, user_data)
        if result:
            flash('User updated successfully!', 'success')
            return redirect(url_for('admin_users'))
        else:
            flash('Failed to update user.', 'danger')

    return render_template('admin_edit_user.html', user=user)

@app.route('/admin/users/toggle/<user_id>', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    result = admin_toggle_user_status(user_id)
    if result:
        flash('User status updated successfully!', 'success')
    else:
        flash('Failed to update user status.', 'danger')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<user_id>', methods=['POST'])
@admin_required
def admin_delete_user_route(user_id):
    result = admin_delete_user(user_id)
    if result:
        flash('User deleted successfully!', 'success')
    else:
        flash('Failed to delete user.', 'danger')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<user_id>/modules', methods=['POST'])
@admin_required
def admin_save_user_modules(user_id):
    # Expecting form data with multiple modules: modules[]
    try:
        modules = request.form.getlist('modules[]') or request.form.getlist('modules') or []
        # Whitelist known module names to avoid arbitrary data
        allowed = ['Purchase', 'Utilization', 'Maintenance', 'Internal Audit', 'Part ID', 'Scrap', 'Fuel', 'Statutory', 'Trip Sheet', 'Log Book', 'DC', 'Accidents/Incidents']
        selected = [m for m in modules if m in allowed]
        # Try updating via Supabase directly so we can return any underlying error message
        try:
            resp = supabase.table('users').update({'modules': selected}).eq('id', user_id).execute()
            # Some clients expose an `error` attribute
            err = getattr(resp, 'error', None)
            data = getattr(resp, 'data', None)
            if err:
                return (f'Failed updating modules: {err}', 400)
            if data:
                return jsonify({'success': True}), 200
            # No rows updated
            return (f'No rows updated while saving modules. Response: {resp}', 400)
        except Exception as e:
            # Fallback to existing helper (keeps older behavior) and include exception text
            try:
                result = admin_update_user(user_id, {'modules': selected})
                if result:
                    return jsonify({'success': True}), 200
            except Exception:
                pass
            return (f'Error saving modules: {str(e)}', 500)
    except Exception as e:
        return (f'Error saving modules: {str(e)}', 500)

# =====================================================
# ADMIN VEHICLE MANAGEMENT ROUTES
# =====================================================

@app.route('/admin/vehicles')
@admin_required
def admin_vehicles():
    # Support per-page and vehicle-id range filters via query params
    per_page = request.args.get('per_page', '25')
    id_from = (request.args.get('id_from') or '').strip()
    id_to = (request.args.get('id_to') or '').strip()

    vehicles = get_all_vehicles()

    # If id range provided, filter vehicles by numeric `vehicle_id` where possible
    if id_from or id_to:
        try:
            start = int(id_from) if id_from else None
        except Exception:
            start = None
        try:
            end = int(id_to) if id_to else None
        except Exception:
            end = None

        filtered = []
        for v in vehicles:
            vid_raw = v.get('vehicle_id')
            vid_int = None
            try:
                vid_int = int(str(vid_raw).strip())
            except Exception:
                try:
                    if isinstance(vid_raw, int):
                        vid_int = vid_raw
                except Exception:
                    vid_int = None

            if vid_int is None:
                # skip entries that don't have numeric vehicle_id
                continue

            if start is not None and end is not None:
                if start <= vid_int <= end:
                    filtered.append(v)
            elif start is not None:
                if vid_int >= start:
                    filtered.append(v)
            elif end is not None:
                if vid_int <= end:
                    filtered.append(v)

        vehicles = filtered

    # Determine rows per page for client-side pagination
    if per_page == 'all':
        js_rows_per_page = len(vehicles) if len(vehicles) > 0 else 1
    else:
        try:
            js_rows_per_page = int(per_page)
            if js_rows_per_page <= 0:
                js_rows_per_page = 25
        except Exception:
            js_rows_per_page = 25

    return render_template('admin_vehicles.html', vehicles=vehicles, rows_per_page=per_page, js_rows_per_page=js_rows_per_page, id_from=id_from, id_to=id_to)


@app.route('/admin/vehicles/inline-update', methods=['POST'])
@admin_required
def admin_vehicles_inline_update():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'success': False, 'error': 'missing payload'}), 400

        vehicle_id = data.get('vehicle_id')
        if not vehicle_id:
            return jsonify({'success': False, 'error': 'missing vehicle_id'}), 400

        # Prepare patch only for allowed fields (dates and editable text fields)
        allowed = ('make', 'model', 'date_of_registration', 'fitness_validity', 'insurance_validity', 'permit_validity', 'pucc_validity', 'tax_validity')
        patch = {}
        for k in allowed:
            if k in data:
                # Normalize empty strings to None
                v = data.get(k) or None
                patch[k] = v

        if not patch:
            return jsonify({'success': False, 'error': 'no updatable fields provided'}), 400

        # Call DB helper
        result = admin_update_vehicle(vehicle_id, patch)
        if result:
            return jsonify({'success': True, 'vehicle': result}), 200
        else:
            return jsonify({'success': False, 'error': 'update failed'}), 500
    except Exception as e:
        try:
            app.logger.exception('Error in inline-update')
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/vehicles/view/<int:vehicle_id>', methods=['GET'])
@admin_required
def admin_view_vehicle(vehicle_id):
    vehicle = get_vehicle_by_id(vehicle_id)
    if not vehicle:
        flash('Vehicle not found!', 'danger')
        return redirect(url_for('admin_vehicles'))
    
    return render_template('admin_view_vehicle.html', vehicle=vehicle)


@app.route('/api/vehicle-by-vehicle-id')
@admin_required
def api_vehicle_by_vehicle_id():
    vid = request.args.get('vehicle_id') or request.args.get('vid')
    if not vid:
        return jsonify({'success': False, 'error': 'missing vehicle_id'}), 400
    try:
        v = get_vehicle_by_vehicle_id(vid)
        if not v:
            return jsonify({'success': False, 'found': False})
        return jsonify({'success': True, 'found': True, 'vehicle': v})
    except Exception as e:
        try:
            app.logger.exception('Error in api_vehicle_by_vehicle_id')
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/vehicles/add', methods=['GET', 'POST'])
@admin_required
def admin_add_vehicle_page():
    if request.method == 'POST':
        vehicle_data = {
            'vehicle_id': request.form.get('vehicle_id'),
            'registration_no': request.form.get('registration_no') or None,
            'date_of_registration': request.form.get('date_of_registration') or None,
            'chassis_number': request.form.get('chassis_number') or None,
            'engine_number': request.form.get('engine_number') or None,
            'fuel_type': request.form.get('fuel_type') or None,
            'emission_norms': request.form.get('emission_norms') or None,
            'vehicle_class': request.form.get('vehicle_class') or None,
            'make': request.form.get('make') or None,
            'model': request.form.get('model') or None,
            'color': request.form.get('color') or None,
            'body_type': request.form.get('body_type') or None,
            'seating_capacity': request.form.get('seating_capacity') or None,
            'unladen_weight': request.form.get('unladen_weight') or None,
            'laden_weight': request.form.get('laden_weight') or None,
            'horse_power': request.form.get('horse_power') or None,
            'cubic_capacity': request.form.get('cubic_capacity') or None,
            'number_of_axles': request.form.get('number_of_axles') or None,
            'no_of_cylinders': request.form.get('no_of_cylinders') or None,
            'month_year_manufacturing': request.form.get('month_year_manufacturing') or None,
            'financier': request.form.get('financier') or None,
            'fitness_validity': request.form.get('fitness_validity') or None,
            'insurance_validity': request.form.get('insurance_validity') or None,
            'insurance_company': request.form.get('insurance_company') or None,
            'permit_validity': request.form.get('permit_validity') or None,
            'permit_district': request.form.get('permit_district') or None,
            'pucc_validity': request.form.get('pucc_validity') or None,
            'tax_validity': request.form.get('tax_validity') or None,
            'registration_validity': request.form.get('registration_validity') or None
        }
        # If a manual vehicle id was provided, prefer that over the select value
        manual_vid = request.form.get('vehicle_id_manual')
        if manual_vid and str(manual_vid).strip() != '':
            vehicle_data['vehicle_id'] = str(manual_vid).strip()

        result = admin_add_vehicle(vehicle_data)
        if result:
            flash('Vehicle added successfully!', 'success')
            return redirect(url_for('admin_vehicles'))
        else:
            flash('Failed to add vehicle. Vehicle ID may already exist.', 'danger')
    
    return render_template('admin_add_vehicle.html')

@app.route('/admin/vehicles/edit/<int:vehicle_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_vehicle(vehicle_id):
    vehicle = get_vehicle_by_id(vehicle_id)
    if not vehicle:
        flash('Vehicle not found!', 'danger')
        return redirect(url_for('admin_vehicles'))
    
    if request.method == 'POST':
        vehicle_data = {
            'vehicle_id': request.form.get('vehicle_id'),
            'registration_no': request.form.get('registration_no') or None,
            'date_of_registration': request.form.get('date_of_registration') or None,
            'chassis_number': request.form.get('chassis_number') or None,
            'engine_number': request.form.get('engine_number') or None,
            'fuel_type': request.form.get('fuel_type') or None,
            'emission_norms': request.form.get('emission_norms') or None,
            'vehicle_class': request.form.get('vehicle_class') or None,
            'make': request.form.get('make') or None,
            'model': request.form.get('model') or None,
            'color': request.form.get('color') or None,
            'body_type': request.form.get('body_type') or None,
            'seating_capacity': request.form.get('seating_capacity') or None,
            'unladen_weight': request.form.get('unladen_weight') or None,
            'laden_weight': request.form.get('laden_weight') or None,
            'horse_power': request.form.get('horse_power') or None,
            'cubic_capacity': request.form.get('cubic_capacity') or None,
            'number_of_axles': request.form.get('number_of_axles') or None,
            'no_of_cylinders': request.form.get('no_of_cylinders') or None,
            'month_year_manufacturing': request.form.get('month_year_manufacturing') or None,
            'financier': request.form.get('financier') or None,
            'fitness_validity': request.form.get('fitness_validity') or None,
            'insurance_validity': request.form.get('insurance_validity') or None,
            'insurance_company': request.form.get('insurance_company') or None,
            'permit_validity': request.form.get('permit_validity') or None,
            'permit_district': request.form.get('permit_district') or None,
            'pucc_validity': request.form.get('pucc_validity') or None,
            'tax_validity': request.form.get('tax_validity') or None,
            'registration_validity': request.form.get('registration_validity') or None
        }
        
        # If a manual vehicle id was provided, prefer that over the select value
        manual_vid = request.form.get('vehicle_id_manual')
        if manual_vid and str(manual_vid).strip() != '':
            vehicle_data['vehicle_id'] = str(manual_vid).strip()

        result = admin_update_vehicle(vehicle_id, vehicle_data)
        if result:
            # Send immediate notification emails for any changed validity dates
            try:
                from datetime import date as _date

                updated_vehicle = {}
                try:
                    if isinstance(vehicle, dict):
                        updated_vehicle = vehicle.copy()
                except Exception:
                    updated_vehicle = {}
                # Merge submitted changes so the email shows latest values
                try:
                    updated_vehicle.update(vehicle_data)
                except Exception:
                    pass

                # Load admin-controlled reminder settings (if any)
                try:
                    settings = get_settings() or {}
                except Exception:
                    settings = {}

                # If immediate notifications are disabled, skip sending
                if not settings.get('immediate_enabled', True):
                    settings = settings  # no-op to keep lint happy
                else:
                    recipients = settings.get('recipients') or None
                    for fk, label in VEHICLE_DATE_FIELDS.items():
                        old_val = vehicle.get(fk) if isinstance(vehicle, dict) else None
                        new_val = vehicle_data.get(fk)
                        if new_val and str(new_val).strip() != '' and str(old_val or '') != str(new_val):
                            parsed = parse_date_str(new_val)
                            try:
                                days_left = (parsed - _date.today()).days if parsed else None
                            except Exception:
                                days_left = None
                            subj, body = format_vehicle_reminder(updated_vehicle, label, days_left if days_left is not None else 'N/A', due_date_iso=(parsed.isoformat() if parsed else None))
                            try:
                                send_email(subj, body, to_addrs=recipients)
                            except Exception:
                                try:
                                    app.logger.exception('Failed to send immediate vehicle update email for %s', fk)
                                except Exception:
                                    pass
            except Exception:
                try:
                    app.logger.exception('Error while sending vehicle update notifications')
                except Exception:
                    pass

            flash('Vehicle updated successfully!', 'success')
            return redirect(url_for('admin_vehicles'))
        else:
            flash('Failed to update vehicle.', 'danger')
    
    return render_template('admin_edit_vehicle.html', vehicle=vehicle)


@app.route('/admin/reminder-settings', methods=['GET', 'POST'])
@admin_required
def admin_reminder_settings():
    try:
        settings = get_settings() or {}
    except Exception:
        settings = {}

    if request.method == 'POST':
        recipients = request.form.get('recipients') or None
        enabled = True if request.form.get('enabled') == 'on' else False
        immediate_enabled = True if request.form.get('immediate_enabled') == 'on' else False
        try:
            reminder_days = int(request.form.get('reminder_days') or settings.get('reminder_days', 15))
        except Exception:
            reminder_days = settings.get('reminder_days', 15)

        new_settings = {
            'recipients': recipients,
            'enabled': enabled,
            'immediate_enabled': immediate_enabled,
            'reminder_days': reminder_days,
            'reminder_hour': settings.get('reminder_hour', 7),
            'reminder_minute': settings.get('reminder_minute', 0)
        }
        save_settings(new_settings)
        flash('Reminder settings saved', 'success')
        return redirect(url_for('admin_reminder_settings'))

    return render_template('admin_reminder_settings.html', settings=settings)

@app.route('/admin/vehicles/delete/<int:vehicle_id>', methods=['POST'])
@admin_required
def admin_delete_vehicle_route(vehicle_id):
    result = admin_delete_vehicle(vehicle_id)
    if result:
        flash('Vehicle deleted successfully!', 'success')
    else:
        flash('Failed to delete vehicle.', 'danger')
    return redirect(url_for('admin_vehicles'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('admin', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# Menu routes
@app.route('/vehicle-profile', methods=['GET', 'POST'])
@login_required
def vehicle_profile():
    if request.method == 'POST':
        # Extract all form data
        vehicle_data = {
            'vehicle_id': request.form.get('vehicle_id'),
            'registration_no': request.form.get('registration_no'),
            
            # Fitness Certificate
            'fitness_due_date': request.form.get('fitness_due') or None,
            'fitness_executed_date': request.form.get('fitness_executed') or None,
            'fitness_next_due_date': request.form.get('fitness_next') or None,
            'fitness_invoice': request.form.get('fitness_invoice'),
            'fitness_expenditure': request.form.get('fitness_exp'),
            'fitness_remarks': request.form.get('fitness_remarks'),
            
            # Insurance
            'insurance_due_date': request.form.get('insurance_due') or None,
            'insurance_executed_date': request.form.get('insurance_executed') or None,
            'insurance_next_due_date': request.form.get('insurance_next') or None,
            'insurance_invoice': request.form.get('insurance_invoice'),
            'insurance_expenditure': request.form.get('insurance_exp'),
            'insurance_remarks': request.form.get('insurance_remarks'),
            
            # Road Tax 1
            'tax1_due_date': request.form.get('tax1_due') or None,
            'tax1_executed_date': request.form.get('tax1_executed') or None,
            'tax1_next_due_date': request.form.get('tax1_next') or None,
            'tax1_invoice': request.form.get('tax1_invoice'),
            'tax1_expenditure': request.form.get('tax1_exp'),
            'tax1_remarks': request.form.get('tax1_remarks'),
            
            # Road Tax 2
            'tax2_due_date': request.form.get('tax2_due') or None,
            'tax2_executed_date': request.form.get('tax2_executed') or None,
            'tax2_next_due_date': request.form.get('tax2_next') or None,
            'tax2_invoice': request.form.get('tax2_invoice'),
            'tax2_expenditure': request.form.get('tax2_exp'),
            'tax2_remarks': request.form.get('tax2_remarks'),
            
            # Road Tax 3
            'tax3_due_date': request.form.get('tax3_due') or None,
            'tax3_executed_date': request.form.get('tax3_executed') or None,
            'tax3_next_due_date': request.form.get('tax3_next') or None,
            'tax3_invoice': request.form.get('tax3_invoice'),
            'tax3_expenditure': request.form.get('tax3_exp'),
            'tax3_remarks': request.form.get('tax3_remarks'),
            
            # Road Tax 4
            'tax4_due_date': request.form.get('tax4_due') or None,
            'tax4_executed_date': request.form.get('tax4_executed') or None,
            'tax4_next_due_date': request.form.get('tax4_next') or None,
            'tax4_invoice': request.form.get('tax4_invoice'),
            'tax4_expenditure': request.form.get('tax4_exp'),
            'tax4_remarks': request.form.get('tax4_remarks'),
            
            # Route Permit
            'permit_due_date': request.form.get('permit_due') or None,
            'permit_executed_date': request.form.get('permit_executed') or None,
            'permit_next_due_date': request.form.get('permit_next') or None,
            'permit_invoice': request.form.get('permit_invoice'),
            'permit_expenditure': request.form.get('permit_exp'),
            'permit_remarks': request.form.get('permit_remarks'),
            
            # Emission Test 1
            'emission1_due_date': request.form.get('emission1_due') or None,
            'emission1_executed_date': request.form.get('emission1_executed') or None,
            'emission1_next_due_date': request.form.get('emission1_next') or None,
            'emission1_invoice': request.form.get('emission1_invoice'),
            'emission1_expenditure': request.form.get('emission1_exp'),
            'emission1_remarks': request.form.get('emission1_remarks'),
            
            # Emission Test 2
            'emission2_due_date': request.form.get('emission2_due') or None,
            'emission2_executed_date': request.form.get('emission2_executed') or None,
            'emission2_next_due_date': request.form.get('emission2_next') or None,
            'emission2_invoice': request.form.get('emission2_invoice'),
            'emission2_expenditure': request.form.get('emission2_exp'),
            'emission2_remarks': request.form.get('emission2_remarks'),
            
            # Speed Governor
            'speed_due_date': request.form.get('speed_due') or None,
            'speed_executed_date': request.form.get('speed_executed') or None,
            'speed_next_due_date': request.form.get('speed_next') or None,
            'speed_invoice': request.form.get('speed_invoice'),
            'speed_expenditure': request.form.get('speed_exp'),
            'speed_remarks': request.form.get('speed_remarks'),
            
            # Fire Extinguisher
            'fire_due_date': request.form.get('fire_due') or None,
            'fire_executed_date': request.form.get('fire_executed') or None,
            'fire_next_due_date': request.form.get('fire_next') or None,
            'fire_invoice': request.form.get('fire_invoice'),
            'fire_expenditure': request.form.get('fire_exp'),
            'fire_remarks': request.form.get('fire_remarks'),
            
            # First Aid
            'firstaid_due_date': request.form.get('firstaid_due') or None,
            'firstaid_executed_date': request.form.get('firstaid_executed') or None,
            'firstaid_next_due_date': request.form.get('firstaid_next') or None,
            'firstaid_invoice': request.form.get('firstaid_invoice'),
            'firstaid_expenditure': request.form.get('firstaid_exp'),
            'firstaid_remarks': request.form.get('firstaid_remarks')
        }
        
        # Validate required fields
        if not vehicle_data['vehicle_id']:
            flash('Please select a vehicle ID', 'danger')
            return redirect(url_for('vehicle_profile'))
        
        # Load existing annual record to compare changes
        try:
            old_record = get_vehicle_annual_record(vehicle_data.get('vehicle_id'))
        except Exception:
            old_record = None

        # Save to database
        result = save_vehicle_annual_record(vehicle_data)

        if result:
            # Send immediate notifications for changed validity fields (if enabled)
            try:
                from datetime import date as _date
                settings = {}
                try:
                    settings = get_settings() or {}
                except Exception:
                    settings = {}

                if settings.get('immediate_enabled', True):
                    recipients = settings.get('recipients') or None
                    # Map vehicle_profile keys to human labels
                    profile_fields = {
                        'fitness_due_date': 'Fitness Validity',
                        'insurance_due_date': 'Insurance Validity',
                        'permit_due_date': 'Permit Validity'
                    }

                    updated_vehicle = {} if not isinstance(old_record, dict) else old_record.copy()
                    try:
                        updated_vehicle.update(vehicle_data)
                    except Exception:
                        pass

                    for fk, label in profile_fields.items():
                        old_val = (old_record.get(fk) if isinstance(old_record, dict) else None)
                        new_val = vehicle_data.get(fk)
                        if new_val and str(new_val).strip() != '' and str(old_val or '') != str(new_val):
                            parsed = parse_date_str(new_val)
                            try:
                                days_left = (parsed - _date.today()).days if parsed else None
                            except Exception:
                                days_left = None
                            subj, body = format_vehicle_reminder(updated_vehicle, label, days_left if days_left is not None else 'N/A', due_date_iso=(parsed.isoformat() if parsed else None))
                            try:
                                send_email(subj, body, to_addrs=recipients)
                            except Exception:
                                try:
                                    app.logger.exception('Failed to send immediate vehicle profile email for %s', fk)
                                except Exception:
                                    pass
            except Exception:
                try:
                    app.logger.exception('Error while sending vehicle profile notifications')
                except Exception:
                    pass

            flash('Vehicle annual record saved successfully!', 'success')
        else:
            flash('Error saving vehicle record. Please try again.', 'danger')

        return redirect(url_for('vehicle_profile'))
    
    return render_template('vehicle_profile.html')

@app.route('/vehicle-profile-permanent', methods=['GET', 'POST'])
@login_required
def vehicle_profile_permanent():
    if request.method == 'POST':
        # Extract all form data
        vehicle_data = {
            'vehicle_id': request.form.get('vehicle_id'),
            'registration_no': request.form.get('registration_no'),
            'registration_number': request.form.get('registration_number'),
            'route_id': request.form.get('route_id'),
            'vehicle_type': request.form.get('vehicle_type'),
            'managing_college': request.form.get('managing_college'),
            'make': request.form.get('make'),
            'modal': request.form.get('modal'),
            'year_manufacturing': request.form.get('year_manufacturing'),
            'year_purchasing': request.form.get('year_purchasing'),
            'engine_number': request.form.get('engine_number'),
            'chassis_number': request.form.get('chassis_number'),
            'speed_governer_id': request.form.get('speed_governer_id'),
            'seating_capacity': request.form.get('seating_capacity')
        }
        
        # Validate required fields
        if not vehicle_data['vehicle_id']:
            flash('Please enter a vehicle ID', 'danger')
            return redirect(url_for('vehicle_profile_permanent'))
        
        # Save to database
        result = save_vehicle_permanent_record(vehicle_data)
        
        if result:
            flash('Vehicle permanent record saved successfully!', 'success')
        else:
            flash('Error saving vehicle permanent record. Please try again.', 'danger')
        
        return redirect(url_for('vehicle_profile_permanent'))
    
    return render_template('vehicle_profile_permanent.html')

@app.route('/trip-opening-attention', methods=['GET', 'POST'])
@login_required
def trip_opening_attention():
    if request.method == 'POST':
        try:
            vehicle_id = request.form.get('vehicle_id')
            registration_no = request.form.get('registration_no', '').upper()
            
            # Get arrays from form
            dates = request.form.getlist('date[]')
            times = request.form.getlist('time[]')
            driver_names = request.form.getlist('driver_name[]')
            kilometer_readings = request.form.getlist('kilometer_reading[]')
            fuel_levels = request.form.getlist('fuel_level[]')
            engine_oil_levels = request.form.getlist('engine_oil_level[]')
            radiator_water_levels = request.form.getlist('radiator_water_level[]')
            vacuum_levels = request.form.getlist('vacuum_level[]')
            tyre_front_lefts = request.form.getlist('tyre_front_left[]')
            tyre_front_rights = request.form.getlist('tyre_front_right[]')
            tyre_rear_lins = request.form.getlist('tyre_rear_lin[]')
            tyre_rear_louts = request.form.getlist('tyre_rear_lout[]')
            tyre_rear_rins = request.form.getlist('tyre_rear_rin[]')
            tyre_rear_routs = request.form.getlist('tyre_rear_rout[]')
            cleanliness_glasses = request.form.getlist('cleanliness_glass[]')
            remarks_list = request.form.getlist('remarks[]')
            
            # Create list of entries
            checklist_entries = []
            for i in range(len(dates)):
                entry = {
                    'vehicle_id': vehicle_id,
                    'registration_no': registration_no,
                    'check_date': dates[i] if dates[i] else None,
                    'check_time': times[i] if times[i] else None,
                    'driver_name': driver_names[i] if i < len(driver_names) else '',
                    'kilometer_reading': kilometer_readings[i] if i < len(kilometer_readings) else '',
                    'fuel_level': fuel_levels[i] if i < len(fuel_levels) else '',
                    'engine_oil_level': engine_oil_levels[i] if i < len(engine_oil_levels) else '',
                    'radiator_water_level': radiator_water_levels[i] if i < len(radiator_water_levels) else '',
                    'vacuum_level': vacuum_levels[i] if i < len(vacuum_levels) else '',
                    'tyre_front_left': tyre_front_lefts[i] if i < len(tyre_front_lefts) else '',
                    'tyre_front_right': tyre_front_rights[i] if i < len(tyre_front_rights) else '',
                    'tyre_rear_lin': tyre_rear_lins[i] if i < len(tyre_rear_lins) else '',
                    'tyre_rear_lout': tyre_rear_louts[i] if i < len(tyre_rear_louts) else '',
                    'tyre_rear_rin': tyre_rear_rins[i] if i < len(tyre_rear_rins) else '',
                    'tyre_rear_rout': tyre_rear_routs[i] if i < len(tyre_rear_routs) else '',
                    'cleanliness_glass': cleanliness_glasses[i] if i < len(cleanliness_glasses) else '',
                    'remarks': remarks_list[i] if i < len(remarks_list) else ''
                }
                checklist_entries.append(entry)
            
            # Save all entries
            saved_count = save_trip_opening_checklist(checklist_entries)
            
            if saved_count > 0:
                flash(f'Successfully saved {saved_count} checklist entry(ies)!', 'success')
            else:
                flash('Error saving checklist entries. Please try again.', 'danger')
        except Exception as e:
            print(f"Error in trip_opening_attention: {e}")
            import traceback
            traceback.print_exc()
            flash('Error processing checklist submission. Please try again.', 'danger')
        
        return redirect(url_for('trip_opening_attention'))
    
    return render_template('trip_opening_attention.html')

@app.route('/utilization-record', methods=['GET', 'POST'])
@login_required
def utilization_record():
    if request.method == 'POST':
        try:
            vehicle_id = request.form.get('vehicle_id')
            registration_no = request.form.get('registration_no', '').upper()
            
            # Get arrays from form
            opening_times = request.form.getlist('opening_time[]')
            opening_kilometers = request.form.getlist('opening_kilometer[]')
            opening_places = request.form.getlist('opening_place[]')
            purpose_trips = request.form.getlist('purpose_trip[]')
            strength_shes = request.form.getlist('strength_she[]')
            strength_hes = request.form.getlist('strength_he[]')
            closing_times = request.form.getlist('closing_time[]')
            closing_kilometers = request.form.getlist('closing_kilometer[]')
            closing_places = request.form.getlist('closing_place[]')
            coverage_times = request.form.getlist('coverage_time[]')
            coverage_kms_list = request.form.getlist('coverage_kms[]')
            
            # Create list of entries
            utilization_entries = []
            for i in range(len(opening_times)):
                entry = {
                    'vehicle_id': vehicle_id,
                    'registration_no': registration_no,
                    'opening_time': opening_times[i] if opening_times[i] else None,
                    'opening_kilometer': opening_kilometers[i] if i < len(opening_kilometers) else '',
                    'opening_place': opening_places[i] if i < len(opening_places) else '',
                    'purpose_trip': purpose_trips[i] if i < len(purpose_trips) else '',
                    'strength_she': strength_shes[i] if i < len(strength_shes) else '',
                    'strength_he': strength_hes[i] if i < len(strength_hes) else '',
                    'closing_time': closing_times[i] if i < len(closing_times) and closing_times[i] else None,
                    'closing_kilometer': closing_kilometers[i] if i < len(closing_kilometers) else '',
                    'closing_place': closing_places[i] if i < len(closing_places) else '',
                    'coverage_time': coverage_times[i] if i < len(coverage_times) else '',
                    'coverage_kms': coverage_kms_list[i] if i < len(coverage_kms_list) else ''
                }
                utilization_entries.append(entry)
            
            # Save all entries
            saved_count = save_utilization_record(utilization_entries)
            
            if saved_count > 0:
                flash(f'Successfully saved {saved_count} utilization record(s)!', 'success')
            else:
                flash('Error saving utilization records. Please try again.', 'danger')
        except Exception as e:
            print(f"Error in utilization_record: {e}")
            import traceback
            traceback.print_exc()
            flash('Error processing utilization record submission. Please try again.', 'danger')
        
        return redirect(url_for('utilization_record'))
    
    return render_template('utilization_record.html')

@app.route('/fuel-consumption', methods=['GET', 'POST'])
@login_required
def fuel_consumption():
    if request.method == 'POST':
        try:
            vehicle_id = request.form.get('vehicle_id', '')
            registration_no = request.form.get('registration_no', '').upper()
            route_id = request.form.get('route_id', '')
            make_model = request.form.get('make_model', '')
            
            # Get arrays from form
            intend_nos = request.form.getlist('intend_no[]')
            dates = request.form.getlist('date[]')
            bill_nos = request.form.getlist('bill_no[]')
            bill_dates = request.form.getlist('bill_date[]')
            bunk_names = request.form.getlist('bunk_name[]')
            qtys = request.form.getlist('qty[]')
            rates = request.form.getlist('rate[]')
            amounts = request.form.getlist('amount[]')
            km_readings = request.form.getlist('km_reading[]')
            driver_names = request.form.getlist('driver_name[]')
            remarks_list = request.form.getlist('remarks[]')
            
            # Create list of entries
            fuel_entries = []
            for i in range(len(dates)):
                entry = {
                    'vehicle_id': vehicle_id,
                    'registration_no': registration_no,
                    'route_id': route_id,
                    'make_model': make_model,
                    'intend_no': intend_nos[i] if i < len(intend_nos) else '',
                    'date': dates[i] if dates[i] else None,
                    'bill_no': bill_nos[i] if i < len(bill_nos) else '',
                    'bill_date': bill_dates[i] if i < len(bill_dates) and bill_dates[i] else None,
                    'bunk_name': bunk_names[i] if i < len(bunk_names) else '',
                    'qty': qtys[i] if i < len(qtys) else '',
                    'rate': rates[i] if i < len(rates) else '',
                    'amount': amounts[i] if i < len(amounts) else '',
                    'km_reading': km_readings[i] if i < len(km_readings) else '',
                    'driver_name': driver_names[i] if i < len(driver_names) else '',
                    'remarks': remarks_list[i] if i < len(remarks_list) else ''
                }
                fuel_entries.append(entry)
            
            # Save all entries
            saved_count = save_fuel_consumption(fuel_entries)
            
            if saved_count > 0:
                flash(f'Successfully saved {saved_count} fuel consumption record(s)!', 'success')
            else:
                flash('Error saving fuel consumption records. Please try again.', 'danger')
        except Exception as e:
            print(f"Error in fuel_consumption: {e}")
            import traceback
            traceback.print_exc()
            flash('Error processing fuel consumption submission. Please try again.', 'danger')
        
        return redirect(url_for('fuel_consumption'))
    
    return render_template('fuel_consumption.html')

@app.route('/daily-technical-remarks', methods=['GET', 'POST'])
@login_required
def daily_technical_remarks():
    if request.method == 'POST':
        try:
            vehicle_id = request.form.get('vehicle_id', '')
            registration_no = request.form.get('registration_no', '').upper()
            
            # Get arrays from form
            dates = request.form.getlist('date[]')
            kilometers = request.form.getlist('kilometer[]')
            drivers_voices = request.form.getlist('drivers_voice[]')
            technical_observations = request.form.getlist('technical_observation[]')
            day_end_statuses = request.form.getlist('day_end_status[]')
            materials_purchased_list = request.form.getlist('materials_purchased[]')
            supplier_bills = request.form.getlist('supplier_bill[]')
            amounts = request.form.getlist('amount[]')
            
            # Create list of entries
            remarks_entries = []
            for i in range(len(dates)):
                entry = {
                    'vehicle_id': vehicle_id,
                    'registration_no': registration_no,
                    'date': dates[i] if dates[i] else None,
                    'kilometer': kilometers[i] if i < len(kilometers) else '',
                    'drivers_voice': drivers_voices[i] if i < len(drivers_voices) else '',
                    'technical_observation': technical_observations[i] if i < len(technical_observations) else '',
                    'day_end_status': day_end_statuses[i] if i < len(day_end_statuses) else '',
                    'materials_purchased': materials_purchased_list[i] if i < len(materials_purchased_list) else '',
                    'supplier_bill': supplier_bills[i] if i < len(supplier_bills) else '',
                    'amount': amounts[i] if i < len(amounts) else ''
                }
                remarks_entries.append(entry)
            
            # Save all entries
            saved_count = save_daily_technical_remarks(remarks_entries)
            
            if saved_count > 0:
                flash(f'Successfully saved {saved_count} technical remark(s)!', 'success')
            else:
                flash('Error saving technical remarks. Please try again.', 'danger')
        except Exception as e:
            print(f"Error in daily_technical_remarks: {e}")
            import traceback
            traceback.print_exc()
            flash('Error processing technical remarks submission. Please try again.', 'danger')
        
        return redirect(url_for('daily_technical_remarks'))
    
    return render_template('daily_technical_remarks.html')

@app.route('/weekly-attention', methods=['GET', 'POST'])
@login_required
def weekly_attention():
    if request.method == 'POST':
        try:
            vehicle_id = request.form.get('vehicle_id', '')
            registration_no = request.form.get('registration_no', '').upper()
            
            # List of 20 processes
            processes = [
                "FLOOR BROOMING",
                "COMPLETE WATER WASHING",
                "TIRONS END GREASING",
                "TYRE INFLATION PHYSICAL EXAM",
                "ENGINE OIL CHECKUP & TOPUP",
                "ANY OTHER OIL SPILLLE CHECKUP",
                "FAN BELTS TENSION CHECKUP",
                "RADIATOR HOSES",
                "FUEL HOSES",
                "BREAK LINING CHECKUP & ADJUSTMENT",
                "CLUTCH FLY & OIL CHECK & ADJUSTMENT",
                "UNDER CHASIS BOLTS CHECK UP",
                "JOINT BOLTS CHECKUP & GREASING",
                "SPRING PLSTS CONDITION CHECKUP",
                "DRINING WATER FROM VACCUM TANK",
                "WIPER CONDITION CHECKUP",
                "FIRE EXTINGUISHER LEVEL",
                "STARTER & ALTERNATOR CHECKUP",
                "BATTERY WATER LEVEL & CONDITION",
                "SEATS CONDITION, SCREWS & BOLTS"
            ]
            
            # Create list of entries (one per process)
            attention_entries = []
            for i, process in enumerate(processes, start=1):
                week1_date = request.form.get(f'week1_date_{i}', '')
                week1_km = request.form.get(f'week1_km_{i}', '')
                week1_obs = request.form.get(f'week1_obs_{i}', '')
                week2_date = request.form.get(f'week2_date_{i}', '')
                week2_km = request.form.get(f'week2_km_{i}', '')
                week2_obs = request.form.get(f'week2_obs_{i}', '')
                
                entry = {
                    'vehicle_id': vehicle_id,
                    'registration_no': registration_no,
                    'process_name': process,
                    'week1_date': week1_date if week1_date else None,
                    'week1_km': week1_km,
                    'week1_obs': week1_obs,
                    'week2_date': week2_date if week2_date else None,
                    'week2_km': week2_km,
                    'week2_obs': week2_obs
                }
                attention_entries.append(entry)
            
            # Save all entries
            saved_count = save_weekly_attention(attention_entries)
            
            if saved_count > 0:
                flash(f'Successfully saved {saved_count} weekly attention record(s)!', 'success')
            else:
                flash('Error saving weekly attention records. Please try again.', 'danger')
        except Exception as e:
            print(f"Error in weekly_attention: {e}")
            import traceback
            traceback.print_exc()
            flash('Error processing weekly attention submission. Please try again.', 'danger')
        
        return redirect(url_for('weekly_attention'))
    
    return render_template('weekly_attention.html')

@app.route('/job-card')
@login_required
def job_card():
    return render_template('job_card.html')

@app.route('/driver-voice', methods=['GET', 'POST'])
@login_required
def driver_voice():
    if request.method == 'POST':
        try:
            vehicle_id = request.form.get('vehicle_id', '')
            registration_no = request.form.get('registration_no', '').upper()
            
            dates = request.form.getlist('date[]')
            times = request.form.getlist('time[]')
            complaints = request.form.getlist('complaints[]')
            suggestions = request.form.getlist('suggestions[]')
            driver_names = request.form.getlist('driver_name[]')
            
            voice_entries = []
            for i in range(len(dates)):
                entry = {
                    'vehicle_id': vehicle_id,
                    'registration_no': registration_no,
                    'date': dates[i] if dates[i] else None,
                    'time': times[i] if times[i] else None,
                    'complaints': complaints[i] if i < len(complaints) else '',
                    'suggestions': suggestions[i] if i < len(suggestions) else '',
                    'driver_name': driver_names[i] if i < len(driver_names) else ''
                }
                voice_entries.append(entry)
            
            saved_count = save_driver_voice(voice_entries)
            
            if saved_count > 0:
                flash(f'Successfully saved {saved_count} driver voice record(s)!', 'success')
            else:
                flash('Error saving driver voice records. Please try again.', 'danger')
        except Exception as e:
            print(f"Error in driver_voice: {e}")
            import traceback
            traceback.print_exc()
            flash('Error processing driver voice submission. Please try again.', 'danger')
        
        return redirect(url_for('driver_voice'))
    
    return render_template('driver_voice.html')

@app.route('/technician-observation')
@login_required
def technician_observation():
    return render_template('technician_observation.html')

@app.route('/technician-observation-works', methods=['POST'])
@login_required
def technician_observation_works():
    try:
        vehicle_id = request.form.get('vehicle_id', '')
        registration_no = request.form.get('registration_no', '').upper()
        
        dates = request.form.getlist('obs_date[]')
        times = request.form.getlist('obs_time[]')
        complaints = request.form.getlist('obs_complaints[]')
        works = request.form.getlist('obs_works[]')
        ta_names = request.form.getlist('obs_ta_name[]')
        
        works_entries = []
        for i in range(len(dates)):
            entry = {
                'vehicle_id': vehicle_id,
                'registration_no': registration_no,
                'date': dates[i] if dates[i] else None,
                'time': times[i] if times[i] else None,
                'complaints': complaints[i] if i < len(complaints) else '',
                'works': works[i] if i < len(works) else '',
                'ta_name': ta_names[i] if i < len(ta_names) else ''
            }
            works_entries.append(entry)
        
        saved_count = save_technician_observation_works(works_entries)
        
        if saved_count > 0:
            flash(f'Successfully saved {saved_count} observation work(s)!', 'success')
        else:
            flash('Error saving observation works. Please try again.', 'danger')
    except Exception as e:
        print(f"Error in technician_observation_works: {e}")
        import traceback
        traceback.print_exc()
        flash('Error processing submission. Please try again.', 'danger')
    
    return redirect(url_for('technician_observation'))

@app.route('/technician-observation-materials', methods=['POST'])
@login_required
def technician_observation_materials():
    try:
        vehicle_id = request.form.get('vehicle_id', '')
        registration_no = request.form.get('registration_no', '').upper()
        
        dates = request.form.getlist('mat_date[]')
        times = request.form.getlist('mat_time[]')
        materials = request.form.getlist('mat_materials[]')
        estimations = request.form.getlist('mat_estimation[]')
        ta_names = request.form.getlist('mat_ta_name[]')
        
        materials_entries = []
        for i in range(len(dates)):
            entry = {
                'vehicle_id': vehicle_id,
                'registration_no': registration_no,
                'date': dates[i] if dates[i] else None,
                'time': times[i] if times[i] else None,
                'materials': materials[i] if i < len(materials) else '',
                'estimation': estimations[i] if i < len(estimations) else '',
                'ta_name': ta_names[i] if i < len(ta_names) else ''
            }
            materials_entries.append(entry)
        
        saved_count = save_technician_observation_materials(materials_entries)
        
        if saved_count > 0:
            flash(f'Successfully saved {saved_count} material estimation(s)!', 'success')
        else:
            flash('Error saving material estimations. Please try again.', 'danger')
    except Exception as e:
        print(f"Error in technician_observation_materials: {e}")
        import traceback
        traceback.print_exc()
        flash('Error processing submission. Please try again.', 'danger')
    
    return redirect(url_for('technician_observation'))

@app.route('/process-of-works', methods=['GET', 'POST'])
@login_required
def process_of_works():
    if request.method == 'POST':
        try:
            vehicle_id = request.form.get('vehicle_id', '')
            registration_no = request.form.get('registration_no', '').upper()
            
            dates = request.form.getlist('date[]')
            times = request.form.getlist('time[]')
            nature_of_works = request.form.getlist('nature_of_work[]')
            rectified_results = request.form.getlist('rectified_results[]')
            bill_nos = request.form.getlist('bill_no[]')
            amounts = request.form.getlist('amount[]')
            
            process_entries = []
            for i in range(len(dates)):
                entry = {
                    'vehicle_id': vehicle_id,
                    'registration_no': registration_no,
                    'date': dates[i] if dates[i] else None,
                    'time': times[i] if times[i] else None,
                    'nature_of_work': nature_of_works[i] if i < len(nature_of_works) else '',
                    'rectified_results': rectified_results[i] if i < len(rectified_results) else '',
                    'bill_no': bill_nos[i] if i < len(bill_nos) else '',
                    'amount': amounts[i] if i < len(amounts) else ''
                }
                process_entries.append(entry)
            
            saved_count = save_process_of_works(process_entries)
            
            if saved_count > 0:
                flash(f'Successfully saved {saved_count} process of work(s)!', 'success')
            else:
                flash('Error saving process of works. Please try again.', 'danger')
        except Exception as e:
            print(f"Error in process_of_works: {e}")
            import traceback
            traceback.print_exc()
            flash('Error processing submission. Please try again.', 'danger')
        
        return redirect(url_for('process_of_works'))
    
    return render_template('process_of_works.html')

@app.route('/monthly-maintenance', methods=['GET', 'POST'])
@login_required
def monthly_maintenance():
    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id', '')
        registration_no = request.form.get('registration_no', '').upper()
        month = request.form.get('month', '')
        
        # Collect data for all 6 processes
        maintenance_data = {
            'vehicle_id': vehicle_id,
            'registration_no': registration_no,
            'month': month
        }
        
        # Extract data for each of the 6 processes
        for i in range(1, 7):
            maintenance_data[f'processed_date_{i}'] = request.form.get(f'processed_date_{i}') or None
            maintenance_data[f'kilometer_reading_{i}'] = request.form.get(f'kilometer_reading_{i}', '')
            maintenance_data[f'action_processed_{i}'] = request.form.get(f'action_processed_{i}', '')
            maintenance_data[f'observation_{i}'] = request.form.get(f'observation_{i}', '')
            maintenance_data[f'parts_used_{i}'] = request.form.get(f'parts_used_{i}', '')
            maintenance_data[f'qty_{i}'] = request.form.get(f'qty_{i}', '')
            maintenance_data[f'supplier_bill_{i}'] = request.form.get(f'supplier_bill_{i}', '')
            maintenance_data[f'value_{i}'] = request.form.get(f'value_{i}', '')
        
        saved_count = save_monthly_maintenance(maintenance_data)
        
        if saved_count > 0:
            flash(f'Successfully saved monthly maintenance record!', 'success')
        else:
            flash('Error saving monthly maintenance record. Please try again.', 'danger')
        
        return redirect(url_for('monthly_maintenance'))
    
    return render_template('monthly_maintenance.html')




@app.route('/halfyearly-maintenance', methods=['GET', 'POST'])
@login_required
def halfyearly_maintenance():
    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id', '')
        registration_no = request.form.get('registration_no', '').upper()
        from_month = request.form.get('from_month', '')
        to_month = request.form.get('to_month', '')
        
        # Collect data for all 6 processes
        maintenance_data = {
            'vehicle_id': vehicle_id,
            'registration_no': registration_no,
            'from_month': from_month,
            'to_month': to_month
        }
        
        # Extract data for each of the 6 processes
        for i in range(1, 7):
            maintenance_data[f'processed_date_{i}'] = request.form.get(f'processed_date_{i}') or None
            maintenance_data[f'kilometer_reading_{i}'] = request.form.get(f'kilometer_reading_{i}', '')
            maintenance_data[f'action_processed_{i}'] = request.form.get(f'action_processed_{i}', '')
            maintenance_data[f'observation_{i}'] = request.form.get(f'observation_{i}', '')
            maintenance_data[f'parts_used_{i}'] = request.form.get(f'parts_used_{i}', '')
            maintenance_data[f'qty_{i}'] = request.form.get(f'qty_{i}', '')
            maintenance_data[f'supplier_bill_{i}'] = request.form.get(f'supplier_bill_{i}', '')
            maintenance_data[f'value_{i}'] = request.form.get(f'value_{i}', '')
        
        saved_count = save_halfyearly_maintenance(maintenance_data)
        
        if saved_count > 0:
            flash(f'Successfully saved half-yearly maintenance record!', 'success')
        else:
            flash('Error saving half-yearly maintenance record. Please try again.', 'danger')
        
        return redirect(url_for('halfyearly_maintenance'))
    
    return render_template('halfyearly_maintenance.html')

@app.route('/annual-maintenance', methods=['GET', 'POST'])
@login_required
def annual_maintenance():
    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id', '')
        registration_no = request.form.get('registration_no', '').upper()
        from_month = request.form.get('from_month', '')
        to_month = request.form.get('to_month', '')
        
        # Collect data for all 26 processes
        maintenance_data = {
            'vehicle_id': vehicle_id,
            'registration_no': registration_no,
            'from_month': from_month,
            'to_month': to_month
        }
        
        # Extract data for each of the 26 processes
        for i in range(1, 27):
            maintenance_data[f'processed_date_{i}'] = request.form.get(f'processed_date_{i}') or None
            maintenance_data[f'kilometer_reading_{i}'] = request.form.get(f'kilometer_reading_{i}', '')
            maintenance_data[f'action_processed_{i}'] = request.form.get(f'action_processed_{i}', '')
            maintenance_data[f'observation_{i}'] = request.form.get(f'observation_{i}', '')
            maintenance_data[f'parts_used_{i}'] = request.form.get(f'parts_used_{i}', '')
            maintenance_data[f'qty_{i}'] = request.form.get(f'qty_{i}', '')
            maintenance_data[f'supplier_bill_{i}'] = request.form.get(f'supplier_bill_{i}', '')
            maintenance_data[f'value_{i}'] = request.form.get(f'value_{i}', '')
        
        saved_count = save_annual_maintenance(maintenance_data)
        
        if saved_count > 0:
            flash(f'Successfully saved annual maintenance record!', 'success')
        else:
            flash('Error saving annual maintenance record. Please try again.', 'danger')
        
        return redirect(url_for('annual_maintenance'))
    
    return render_template('annual_maintenance.html')

@app.route('/annual-summary')
@login_required
def annual_summary():
    return render_template('annual_summary.html')

@app.route('/annual-summary-complaints', methods=['POST'])
@login_required
def annual_summary_complaints():
    vehicle_id = request.form.get('vehicle_id', '')
    registration_no = request.form.get('registration_no', '').upper()
    from_year = request.form.get('from_year', '')
    to_year = request.form.get('to_year', '')
    
    # Extract arrays from form
    dates = request.form.getlist('sum_date[]')
    complaints = request.form.getlist('sum_complaint[]')
    actions = request.form.getlist('sum_action[]')
    statuses = request.form.getlist('sum_status[]')
    
    # Create entry dictionaries
    complaint_entries = []
    for i in range(len(dates)):
        entry = {
            'vehicle_id': vehicle_id,
            'registration_no': registration_no,
            'from_year': from_year,
            'to_year': to_year,
            'date': dates[i] if dates[i] else None,
            'complaint': complaints[i] if i < len(complaints) else '',
            'action_taken': actions[i] if i < len(actions) else '',
            'status': statuses[i] if i < len(statuses) else ''
        }
        complaint_entries.append(entry)
    
    saved_count = save_annual_summary_complaints(complaint_entries)
    
    if saved_count > 0:
        flash(f'Successfully saved {saved_count} annual summary complaint(s)!', 'success')
    else:
        flash('Error saving annual summary complaints. Please try again.', 'danger')
    
    return redirect(url_for('annual_summary'))

@app.route('/annual-summary-recommendations', methods=['POST'])
@login_required
def annual_summary_recommendations():
    vehicle_id = request.form.get('rec_vehicle_id', '')
    registration_no = request.form.get('rec_registration_no', '').upper()
    recommendation_year = request.form.get('rec_year', '')
    
    # Extract arrays from form
    dates = request.form.getlist('rec_approx_date[]')
    complaints = request.form.getlist('rec_complaint[]')
    preventions = request.form.getlist('rec_prevention[]')
    remarks = request.form.getlist('rec_remarks[]')
    
    # Create entry dictionaries
    recommendation_entries = []
    for i in range(len(dates)):
        entry = {
            'vehicle_id': vehicle_id,
            'registration_no': registration_no,
            'recommendation_year': recommendation_year,
            'approx_date': dates[i] if dates[i] else None,
            'anticipated_complaint': complaints[i] if i < len(complaints) else '',
            'prevention': preventions[i] if i < len(preventions) else '',
            'remarks': remarks[i] if i < len(remarks) else ''
        }
        recommendation_entries.append(entry)
    
    saved_count = save_annual_summary_recommendations(recommendation_entries)
    
    if saved_count > 0:
        flash(f'Successfully saved {saved_count} annual summary recommendation(s)!', 'success')
    else:
        flash('Error saving annual summary recommendations. Please try again.', 'danger')
    
    return redirect(url_for('annual_summary'))

@app.route('/incidents-reports')
@login_required
def incidents_reports():
    return render_template('incidents_reports.html')

@app.route('/incidents-reports-incidents', methods=['POST'])
@login_required
def incidents_reports_incidents():
    vehicle_id = request.form.get('vehicle_id', '')
    registration_no = request.form.get('registration_no', '').upper()
    from_year = request.form.get('from_year', '')
    to_year = request.form.get('to_year', '')
    
    # Extract arrays from form
    dates = request.form.getlist('inc_date[]')
    natures = request.form.getlist('inc_nature[]')
    reasons = request.form.getlist('inc_reasons[]')
    responsibles = request.form.getlist('inc_responsible[]')
    
    # Create entry dictionaries
    incident_entries = []
    for i in range(len(dates)):
        entry = {
            'vehicle_id': vehicle_id,
            'registration_no': registration_no,
            'from_year': from_year,
            'to_year': to_year,
            'date': dates[i] if dates[i] else None,
            'nature_of_incident': natures[i] if i < len(natures) else '',
            'reasons_causes': reasons[i] if i < len(reasons) else '',
            'responsible': responsibles[i] if i < len(responsibles) else ''
        }
        incident_entries.append(entry)
    
    saved_count = save_incidents_reports_incidents(incident_entries)
    
    if saved_count > 0:
        flash(f'Successfully saved {saved_count} incident(s)!', 'success')
    else:
        flash('Error saving incidents. Please try again.', 'danger')
    
    return redirect(url_for('incidents_reports'))

# ──────────────────────────────────────────────────────────────
# Accidents / Incidents Module
# ──────────────────────────────────────────────────────────────

@app.route('/accidents-incidents')
@login_required
@module_required('Accidents/Incidents')
def accidents_incidents():
    """New Accidents / Incidents entry form."""
    vehicles = get_all_vehicles() or []
    # fetch employees for driver select
    try:
        emp_resp = supabase.table('employees').select('employee_id, name').order('employee_id').execute()
        employees = emp_resp.data or []
    except Exception:
        employees = []
    entry_no = get_next_accident_entry_no()
    from datetime import datetime as _dt
    now_str = _dt.now().strftime('%Y-%m-%dT%H:%M')
    return render_template('incidents.html',
                           vehicles=vehicles,
                           employees=employees,
                           entry_no=entry_no,
                           now_str=now_str)


@app.route('/accidents-incidents/save', methods=['POST'])
@login_required
@module_required('Accidents/Incidents')
def accidents_incidents_save():
    """Save a new Accidents / Incidents record."""
    f = request.form
    def _get(key, default=''):
        return (f.get(key) or default).strip()

    data = {
        'entry_no':                 _get('entry_no'),
        'date_time':                _get('date_time') or datetime.now().isoformat(),
        'vehicle_id':               _get('vehicle_id'),
        'registration_no':          _get('registration_no').upper(),
        'driver_id':                _get('driver_id'),
        'driver_name':              _get('driver_name').upper(),
        'place_of_incident':        _get('place_of_incident'),
        'place_description':        _get('place_description'),
        'type_of_incident':         _get('type_of_incident'),
        'type_of_incident_desc':    _get('type_of_incident_desc'),
        'type_of_loss':             _get('type_of_loss'),
        'type_of_loss_desc':        _get('type_of_loss_desc'),
        'case_description':         _get('case_description'),
        'hospitalized':             _get('hospitalized', 'NO'),
        'hospital_name':            _get('hospital_name'),
        'type_of_treatment':        _get('type_of_treatment'),
        'treatment_expenditure':    f.get('treatment_expenditure') or None,
        'case_filed_police':        _get('case_filed_police', 'NO'),
        'fir_csr_no':               _get('fir_csr_no'),
        'police_date':              f.get('police_date') or None,
        'police_status':            _get('police_status'),
        'police_closed_date':       f.get('police_closed_date') or None,
        'settled_in_person':        _get('settled_in_person', 'NO'),
        'minutes_of_settlement':    _get('minutes_of_settlement'),
        'settlement_status':        _get('settlement_status', 'PENDING'),
        'settlement_closed_date':   f.get('settlement_closed_date') or None,
        'police_total_paid':        f.get('police_total_paid') or None,
        'settlement_amount':        f.get('settlement_amount') or None,
        'total_loss':               f.get('total_loss') or None,
    }

    # Settlement persons list
    settlement_persons = f.getlist('settlement_person[]')

    record = save_accident_incident(data, settlement_persons)
    if record:
        flash(f"Accident/Incident saved successfully! Entry No: {data['entry_no']}", 'success')
        return redirect(url_for('accidents_incidents_view', incident_id=record['id']))
    else:
        flash('Error saving record. Please try again.', 'danger')
        return redirect(url_for('accidents_incidents'))


@app.route('/accidents-incidents/list')
@login_required
@module_required('Accidents/Incidents')
def accidents_incidents_list():
    """History list of all Accidents / Incidents."""
    records = get_all_accidents_incidents()
    return render_template('incidents_list.html', records=records)


@app.route('/accidents-incidents/<int:incident_id>')
@login_required
@module_required('Accidents/Incidents')
def accidents_incidents_view(incident_id):
    """View / print a single Accidents / Incidents record."""
    record = get_accident_incident_by_id(incident_id)
    if not record:
        flash('Record not found.', 'danger')
        return redirect(url_for('accidents_incidents_list'))
    return render_template('incidents_view.html', record=record)


# ──────────────────────────────────────────────────────────────
# API: fetch vehicle registration by vehicle_id (for auto-fill)
# ──────────────────────────────────────────────────────────────
@app.route('/api/vehicle-reg/<path:vehicle_id_val>')
@login_required
def api_vehicle_reg(vehicle_id_val):
    veh = get_vehicle_by_vehicle_id(vehicle_id_val)
    if veh:
        return jsonify({'registration_no': veh.get('registration_no', '')})
    return jsonify({'registration_no': ''})


# ──────────────────────────────────────────────────────────────
# API: fetch driver name by employee_id (for incidents auto-fill)
# ──────────────────────────────────────────────────────────────
@app.route('/api/driver-name/<path:driver_id_val>')
@login_required
def api_driver_name(driver_id_val):
    try:
        app.logger.debug('api_driver_name lookup for: %s', driver_id_val)
        resp = supabase.table('employees').select('employee_id,name,full_name,employee_name').eq('employee_id', driver_id_val).execute()
        app.logger.debug('supabase response: %s', getattr(resp, 'data', None))
        if resp.data:
            row = resp.data[0]
            name = row.get('name') or row.get('full_name') or row.get('employee_name') or ''
            return jsonify({'success': True, 'driver_name': name})
        return jsonify({'success': False, 'driver_name': ''}), 404
    except Exception as e:
        app.logger.exception('api_driver_name error for %s: %s', driver_id_val, e)
        return jsonify({'success': False, 'driver_name': '', 'error': str(e)}), 500


@login_required
def incidents_reports_claims():
    vehicle_id = request.form.get('claim_vehicle_id', '')
    registration_no = request.form.get('claim_registration_no', '').upper()
    from_year = request.form.get('claim_from_year', '')
    to_year = request.form.get('claim_to_year', '')
    
    # Extract arrays from form
    dates = request.form.getlist('claim_date[]')
    natures = request.form.getlist('claim_nature[]')
    modes = request.form.getlist('claim_mode[]')
    values = request.form.getlist('claim_value[]')
    
    # Create entry dictionaries
    claim_entries = []
    for i in range(len(dates)):
        entry = {
            'vehicle_id': vehicle_id,
            'registration_no': registration_no,
            'from_year': from_year,
            'to_year': to_year,
            'approx_date': dates[i] if dates[i] else None,
            'nature_of_claim': natures[i] if i < len(natures) else '',
            'mode_of_claim': modes[i] if i < len(modes) else '',
            'claim_value_responsible': values[i] if i < len(values) else ''
        }
        claim_entries.append(entry)
    
    saved_count = save_incidents_reports_claims(claim_entries)
    
    if saved_count > 0:
        flash(f'Successfully saved {saved_count} claim(s)!', 'success')
    else:
        flash('Error saving claims. Please try again.', 'danger')
    
    return redirect(url_for('incidents_reports'))

@app.route('/feedback')
@login_required
def feedback():
    return render_template('feedback.html')

@app.route('/feedback-submit', methods=['POST'])
@login_required
def feedback_submit():
    feedback_data = {
        'name': request.form.get('name', ''),
        'email': request.form.get('email', ''),
        'contact': request.form.get('contact', ''),
        'department': request.form.get('department', ''),
        'feedback_type': request.form.get('feedback_type', ''),
        'subject': request.form.get('subject', ''),
        'message': request.form.get('message', ''),
        'rating': int(request.form.get('rating')) if request.form.get('rating') else None
    }
    
    saved_count = save_feedback(feedback_data)
    
    if saved_count > 0:
        flash('Thank you for your feedback! We appreciate your input.', 'success')
    else:
        flash('Error submitting feedback. Please try again.', 'danger')
    
    return redirect(url_for('feedback'))

# =====================================================
# HR EMPLOYEE MANAGEMENT ROUTES
# =====================================================

@app.route('/hr/employees')
@admin_required
def hr_employees():
    """Display all employees"""
    try:
        response = supabase.table('employees').select('*').order('created_at', desc=True).execute()
        employees = response.data if response.data else []
        
        # Calculate stats
        total_count = len(employees)
        active_count = len([e for e in employees if e.get('status') == 'active'])
        inactive_count = total_count - active_count
        
        return render_template('hr_employees.html', 
                               employees=employees,
                               total_count=total_count,
                               active_count=active_count,
                               inactive_count=inactive_count)
    except Exception as e:
        print(f"Error fetching employees: {e}")
        flash(f'Error loading employees: {str(e)}', 'danger')
        return render_template('hr_employees.html', 
                               employees=[],
                               total_count=0,
                               active_count=0,
                               inactive_count=0)


@app.route('/api/employee/<path:employee_id>')
@login_required
def api_get_employee(employee_id):
    """Return employee record by employee_id (used for autofill in forms)."""
    try:
        # employee_id is a string like 'PMCTECH/LOGI/EMP001' or simple code
        res = supabase.table('employees').select('*').eq('employee_id', employee_id).limit(1).execute()
        if res.data and len(res.data) > 0:
            emp = res.data[0]
            return jsonify({'success': True, 'employee': emp}), 200
        return jsonify({'success': False, 'message': 'Employee not found'}), 404
    except Exception as e:
        app.logger.exception('Failed to fetch employee %s', employee_id)
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/hr/employees/add', methods=['GET', 'POST'])
@admin_required
def hr_add_employee():
    """Add new employee"""
    if request.method == 'POST':
        try:
            # Get next employee ID in format PMCTECH/LOGI/EMP001
            try:
                # Get current count of employees to generate next ID
                result = supabase.table('employees').select('id').execute()
                count = len(result.data) if result.data else 0
                employee_id = f"PMCTECH/LOGI/EMP{str(count + 1).zfill(3)}"
            except:
                # Fallback: Get count and generate ID
                count = len(supabase.table('employees').select('id').execute().data or [])
                employee_id = f"PMCTECH/LOGI/EMP{str(count + 1).zfill(3)}"
            
            # Parse experience data
            experience_data = []
            exp_years = request.form.getlist('exp_years[]')
            exp_designation = request.form.getlist('exp_designation[]')
            exp_organization = request.form.getlist('exp_organization[]')
            exp_vehicle = request.form.getlist('exp_vehicle[]')
            
            for i in range(len(exp_years)):
                if exp_years[i]:
                    experience_data.append({
                        'years': exp_years[i],
                        'designation': exp_designation[i] if i < len(exp_designation) else '',
                        'organization': exp_organization[i] if i < len(exp_organization) else '',
                        'vehicle_type': exp_vehicle[i] if i < len(exp_vehicle) else ''
                    })
            
            # Parse accidents data
            accidents_data = []
            acc_dates = request.form.getlist('acc_date[]')
            acc_descriptions = request.form.getlist('acc_description[]')
            acc_types = request.form.getlist('acc_type[]')
            acc_case_nos = request.form.getlist('acc_case_no[]')
            acc_statuses = request.form.getlist('acc_status[]')
            
            for i in range(len(acc_dates)):
                if acc_dates[i]:
                    accidents_data.append({
                        'date': acc_dates[i],
                        'description': acc_descriptions[i] if i < len(acc_descriptions) else '',
                        'type': acc_types[i] if i < len(acc_types) else '',
                        'case_no': acc_case_nos[i] if i < len(acc_case_nos) else '',
                        'status': acc_statuses[i] if i < len(acc_statuses) else ''
                    })
            
            # Parse awards data
            awards_data = []
            award_dates = request.form.getlist('award_date[]')
            award_natures = request.form.getlist('award_nature[]')
            award_remarks = request.form.getlist('award_remarks[]')
            
            for i in range(len(award_dates)):
                if award_dates[i]:
                    awards_data.append({
                        'date': award_dates[i],
                        'nature': award_natures[i] if i < len(award_natures) else '',
                        'remarks': award_remarks[i] if i < len(award_remarks) else ''
                    })
            
            employee_data = {
                'employee_id': employee_id,
                'name': request.form.get('name'),
                'profile_post': request.form.get('profile_post'),
                'profile_post_other': request.form.get('profile_post_other'),
                'blood_group': request.form.get('blood_group'),
                'age': request.form.get('age') or None,
                'dl_no': request.form.get('dl_no'),
                'date_of_birth': request.form.get('date_of_birth') or None,
                'date_of_issue': request.form.get('date_of_issue') or None,
                'badge_no': request.form.get('badge_no'),
                'lmv_date_of_issue': request.form.get('lmv_date_of_issue') or None,
                'rto_ref': request.form.get('rto_ref'),
                'hmv_date_of_issue': request.form.get('hmv_date_of_issue') or None,
                'validity_nt': request.form.get('validity_nt') or None,
                'validity_tr': request.form.get('validity_tr') or None,
                'aadhar_no': request.form.get('aadhar_no'),
                'nativity': request.form.get('nativity'),
                'experience': experience_data,
                'accidents': accidents_data,
                'awards': awards_data,
                'vision': request.form.get('vision'),
                'vision_r': request.form.get('vision_r'),
                'vision_l': request.form.get('vision_l'),
                'vision_checkup_date': request.form.get('vision_checkup_date') or None,
                'hearing': request.form.get('hearing'),
                'hearing_r': request.form.get('hearing_r'),
                'hearing_l': request.form.get('hearing_l'),
                'hearing_checkup_date': request.form.get('hearing_checkup_date') or None,
                'bp': request.form.get('bp'),
                'bp_checkup_date': request.form.get('bp_checkup_date') or None,
                'sugar': request.form.get('sugar'),
                'sugar_checkup_date': request.form.get('sugar_checkup_date') or None,
                'fractures': request.form.get('fractures'),
                'fractures_checkup_date': request.form.get('fractures_checkup_date') or None,
                'alcohol': request.form.get('alcohol'),
                'gutkha': request.form.get('gutkha'),
                'smoking': request.form.get('smoking'),
                'gambling': request.form.get('gambling'),
                'tobacco': request.form.get('tobacco'),
                'other_habits': request.form.get('other_habits'),
                'father_name': request.form.get('father_name'),
                'father_age': request.form.get('father_age') or None,
                'father_occupation': request.form.get('father_occupation'),
                'father_gender': request.form.get('father_gender'),
                'mother_name': request.form.get('mother_name'),
                'mother_age': request.form.get('mother_age') or None,
                'mother_occupation': request.form.get('mother_occupation'),
                'mother_gender': request.form.get('mother_gender'),
                'spouse_name': request.form.get('spouse_name'),
                'spouse_age': request.form.get('spouse_age') or None,
                'spouse_occupation': request.form.get('spouse_occupation'),
                'spouse_gender': request.form.get('spouse_gender'),
                'child1_name': request.form.get('child1_name'),
                'child1_age': request.form.get('child1_age') or None,
                'child1_occupation': request.form.get('child1_occupation'),
                'child1_gender': request.form.get('child1_gender'),
                'child2_name': request.form.get('child2_name'),
                'child2_age': request.form.get('child2_age') or None,
                'child2_occupation': request.form.get('child2_occupation'),
                'child2_gender': request.form.get('child2_gender'),
                'child3_name': request.form.get('child3_name'),
                'child3_age': request.form.get('child3_age') or None,
                'child3_occupation': request.form.get('child3_occupation'),
                'child3_gender': request.form.get('child3_gender'),
                'max_education': request.form.get('max_education'),
                'school': request.form.get('school'),
                'mother_tongue': request.form.get('mother_tongue'),
                'other_lang': request.form.get('other_lang'),
                'nationality': request.form.get('nationality'),
                'community_caste': request.form.get('community_caste'),
                'religion': request.form.get('religion'),
                'permanent_address': request.form.get('permanent_address'),
                'present_address': request.form.get('present_address'),
                'phone_no': request.form.get('phone_no'),
                'whatsapp_phone_no': request.form.get('whatsapp_phone_no'),
                'number_phone_no': request.form.get('number_phone_no'),
                'nominee_name': request.form.get('nominee_name'),
                'nominee_phone_no': request.form.get('nominee_phone_no'),
                'nominee_relation': request.form.get('nominee_relation'),
                'nominee_gender': request.form.get('nominee_gender'),
                'date_of_joining': request.form.get('date_of_joining') or None,
                'driving_nature': request.form.get('driving_nature'),
                'route': request.form.get('route'),
                'reference': request.form.get('reference'),
                'expected_salary': request.form.get('expected_salary'),
                # Basic salary (optional numeric)
                'basic_salary': (lambda v: float(v) if (v is not None and str(v).strip() != '') else None)(request.form.get('basic_salary')),
                'expected_date_of_joining': request.form.get('expected_date_of_joining') or None,
                'status': 'active',
                'bank_name': request.form.get('bank_name'),
                'account_number': request.form.get('account_number'),
                'account_holder_name': request.form.get('account_holder_name'),
                'ifsc_code': request.form.get('ifsc_code'),
                'branch': request.form.get('branch'),
                'account_type': request.form.get('account_type'),
                'created_by': session.get('admin')
            }
            
            response = supabase.table('employees').insert(employee_data).execute()
            
            if response.data:
                # Redirect with success parameter, employee_id and date_of_joining for popup
                return redirect(url_for('hr_add_employee', success='true', employee_id=employee_id, date_of_joining=employee_data.get('date_of_joining')))
            else:
                flash('Error adding employee. Please try again.', 'danger')
        except Exception as e:
            print(f"Error adding employee: {e}")
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('hr_add_employee.html')

@app.route('/hr/employees/<path:employee_id>/profile')
@admin_required
def hr_employee_profile(employee_id):
    """View employee profile"""
    try:
        response = supabase.table('employees').select('*').eq('employee_id', employee_id).execute()
        
        if response.data and len(response.data) > 0:
            employee = response.data[0]
            return render_template('hr_employee_profile.html', employee=employee)
        else:
            flash('Employee not found', 'danger')
            return redirect(url_for('hr_employees'))
    except Exception as e:
        print(f"Error fetching employee profile: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('hr_employees'))

@app.route('/hr/employees/<path:employee_id>/edit', methods=['GET', 'POST'])
@admin_required
def hr_edit_employee(employee_id):
    """Edit employee"""
    try:
        response = supabase.table('employees').select('*').eq('employee_id', employee_id).execute()
        
        if not response.data or len(response.data) == 0:
            flash('Employee not found', 'danger')
            return redirect(url_for('hr_employees'))
        
        employee = response.data[0]
        
        if request.method == 'POST':
            # Parse experience data
            experience_data = []
            exp_from_date = request.form.getlist('exp_from_date[]')
            exp_to_date = request.form.getlist('exp_to_date[]')
            exp_designation = request.form.getlist('exp_designation[]')
            exp_organization = request.form.getlist('exp_organization[]')
            exp_vehicle = request.form.getlist('exp_vehicle[]')
            
            for i in range(len(exp_from_date)):
                if exp_from_date[i]:
                    experience_data.append({
                        'from_date': exp_from_date[i],
                        'to_date': exp_to_date[i] if i < len(exp_to_date) else '',
                        'designation': exp_designation[i] if i < len(exp_designation) else '',
                        'organization': exp_organization[i] if i < len(exp_organization) else '',
                        'vehicle_type': exp_vehicle[i] if i < len(exp_vehicle) else ''
                    })
            
            # Parse accidents data
            accidents_data = []
            acc_dates = request.form.getlist('acc_date[]')
            acc_descriptions = request.form.getlist('acc_description[]')
            acc_types = request.form.getlist('acc_type[]')
            acc_case_nos = request.form.getlist('acc_case_no[]')
            acc_statuses = request.form.getlist('acc_status[]')
            
            for i in range(len(acc_dates)):
                if acc_dates[i]:
                    accidents_data.append({
                        'date': acc_dates[i],
                        'description': acc_descriptions[i] if i < len(acc_descriptions) else '',
                        'type': acc_types[i] if i < len(acc_types) else '',
                        'case_no': acc_case_nos[i] if i < len(acc_case_nos) else '',
                        'status': acc_statuses[i] if i < len(acc_statuses) else ''
                    })
            
            # Parse awards data
            awards_data = []
            award_dates = request.form.getlist('award_date[]')
            award_natures = request.form.getlist('award_nature[]')
            award_remarks = request.form.getlist('award_remarks[]')
            
            for i in range(len(award_dates)):
                if award_dates[i]:
                    awards_data.append({
                        'date': award_dates[i],
                        'nature': award_natures[i] if i < len(award_natures) else '',
                        'remarks': award_remarks[i] if i < len(award_remarks) else ''
                    })
            
            update_data = {
                'profile_post': request.form.get('profile_post'),
                'profile_post_other': request.form.get('profile_post_other'),
                'blood_group': request.form.get('blood_group'),
                'name': request.form.get('name'),
                'age': request.form.get('age') or None,
                'dl_no': request.form.get('dl_no'),
                'date_of_birth': request.form.get('date_of_birth') or None,
                'date_of_issue': request.form.get('date_of_issue') or None,
                'badge_no': request.form.get('badge_no'),
                'lmv_date_of_issue': request.form.get('lmv_date_of_issue') or None,
                'rto_ref': request.form.get('rto_ref'),
                'hmv_date_of_issue': request.form.get('hmv_date_of_issue') or None,
                'validity_nt': request.form.get('validity_nt') or None,
                'validity_tr': request.form.get('validity_tr') or None,
                'aadhar_no': request.form.get('aadhar_no'),
                'nativity': request.form.get('nativity'),
                'experience': experience_data,
                'accidents': accidents_data,
                'awards': awards_data,
                'vision': request.form.get('vision'),
                'vision_r': request.form.get('vision_r'),
                'vision_l': request.form.get('vision_l'),
                'vision_checkup_date': request.form.get('vision_checkup_date') or None,
                'hearing': request.form.get('hearing'),
                'hearing_r': request.form.get('hearing_r'),
                'hearing_l': request.form.get('hearing_l'),
                'hearing_checkup_date': request.form.get('hearing_checkup_date') or None,
                'bp': request.form.get('bp'),
                'bp_checkup_date': request.form.get('bp_checkup_date') or None,
                'sugar': request.form.get('sugar'),
                'sugar_checkup_date': request.form.get('sugar_checkup_date') or None,
                'fractures': request.form.get('fractures'),
                'fractures_checkup_date': request.form.get('fractures_checkup_date') or None,
                'alcohol': request.form.get('alcohol'),
                'gutkha': request.form.get('gutkha'),
                'smoking': request.form.get('smoking'),
                'gambling': request.form.get('gambling'),
                'tobacco': request.form.get('tobacco'),
                'other_habits': request.form.get('other_habits'),
                'father_name': request.form.get('father_name'),
                'father_age': request.form.get('father_age') or None,
                'father_occupation': request.form.get('father_occupation'),
                'father_gender': request.form.get('father_gender'),
                'mother_name': request.form.get('mother_name'),
                'mother_age': request.form.get('mother_age') or None,
                'mother_occupation': request.form.get('mother_occupation'),
                'mother_gender': request.form.get('mother_gender'),
                'spouse_name': request.form.get('spouse_name'),
                'spouse_age': request.form.get('spouse_age') or None,
                'spouse_occupation': request.form.get('spouse_occupation'),
                'spouse_gender': request.form.get('spouse_gender'),
                'child1_name': request.form.get('child1_name'),
                'child1_age': request.form.get('child1_age') or None,
                'child1_occupation': request.form.get('child1_occupation'),
                'child1_gender': request.form.get('child1_gender'),
                'child2_name': request.form.get('child2_name'),
                'child2_age': request.form.get('child2_age') or None,
                'child2_occupation': request.form.get('child2_occupation'),
                'child2_gender': request.form.get('child2_gender'),
                'child3_name': request.form.get('child3_name'),
                'child3_age': request.form.get('child3_age') or None,
                'child3_occupation': request.form.get('child3_occupation'),
                'child3_gender': request.form.get('child3_gender'),
                'max_education': request.form.get('max_education'),
                'school': request.form.get('school'),
                'mother_tongue': request.form.get('mother_tongue'),
                'other_lang': request.form.get('other_lang'),
                'nationality': request.form.get('nationality'),
                'community_caste': request.form.get('community_caste'),
                'religion': request.form.get('religion'),
                'permanent_address': request.form.get('permanent_address'),
                'present_address': request.form.get('present_address'),
                'phone_no': request.form.get('phone_no'),
                'whatsapp_phone_no': request.form.get('whatsapp_phone_no'),
                'number_phone_no': request.form.get('number_phone_no'),
                'nominee_name': request.form.get('nominee_name'),
                'nominee_phone_no': request.form.get('nominee_phone_no'),
                'nominee_relation': request.form.get('nominee_relation'),
                'nominee_gender': request.form.get('nominee_gender'),
                'date_of_joining': request.form.get('date_of_joining') or None,
                'driving_nature': request.form.get('driving_nature'),
                'route': request.form.get('route'),
                'reference': request.form.get('reference'),
                'expected_salary': request.form.get('expected_salary'),
                'expected_date_of_joining': request.form.get('expected_date_of_joining') or None,
                # Basic salary (optional numeric)
                'basic_salary': (lambda v: float(v) if (v is not None and str(v).strip() != '') else None)(request.form.get('basic_salary')),
                'bank_name': request.form.get('bank_name'),
                'account_number': request.form.get('account_number'),
                'account_holder_name': request.form.get('account_holder_name'),
                'ifsc_code': request.form.get('ifsc_code'),
                'branch': request.form.get('branch'),
                'account_type': request.form.get('account_type'),
                'status': request.form.get('status', 'active')
            }
            
            response = supabase.table('employees').update(update_data).eq('employee_id', employee_id).execute()
            
            if response.data:
                flash(f'Employee {employee_id} updated successfully!', 'success')
                return redirect(url_for('hr_employee_profile', employee_id=employee_id))
            else:
                flash('Error updating employee. Please try again.', 'danger')
        
        return render_template('hr_add_employee.html', employee=employee, edit_mode=True)
    except Exception as e:
        print(f"Error editing employee: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('hr_employees'))

# =====================================================
# VENDOR MANAGEMENT ROUTES (Purchase Head)
# =====================================================

@app.route('/admin/vendors')
@admin_required
def admin_vendors():
    """Display all vendors"""
    try:
        response = supabase.table('vendors').select('*').order('created_at', desc=True).execute()
        vendors = response.data if response.data else []
        
        # Calculate stats
        total_count = len(vendors)
        approved_count = len([v for v in vendors if v.get('approval_status') == 'approved'])
        pending_count = len([v for v in vendors if v.get('approval_status') == 'pending'])
        active_count = len([v for v in vendors if v.get('status') == 'active'])
        
        return render_template('admin_vendors.html', 
                             vendors=vendors,
                             total_count=total_count,
                             approved_count=approved_count,
                             pending_count=pending_count,
                             active_count=active_count)
    except Exception as e:
        print(f"Error loading vendors: {e}")
        flash(f'Error loading vendors: {str(e)}', 'danger')
        return render_template('admin_vendors.html', vendors=[], total_count=0, approved_count=0, pending_count=0, active_count=0)

@app.route('/admin/vendors/add', methods=['GET', 'POST'])
@admin_required
def admin_add_vendor():
    """Add new vendor"""
    if request.method == 'POST':
        try:
            # Get next vendor ID using database function
            try:
                vendor_id_response = supabase.rpc('get_next_vendor_id').execute()
                vendor_id = vendor_id_response.data if vendor_id_response.data else None
            except:
                # Fallback: generate manually if function doesn't exist
                response = supabase.table('vendors').select('vendor_id').order('created_at', desc=True).limit(1).execute()
                if response.data and len(response.data) > 0:
                    last_id = response.data[0]['vendor_id']
                    import re
                    match = re.search(r'VEN(\d+)', last_id)
                    if match:
                        num = int(match.group(1)) + 1
                        vendor_id = f'PMC-LOGI-VEN{str(num).zfill(3)}'
                    else:
                        vendor_id = 'PMC-LOGI-VEN001'
                else:
                    vendor_id = 'PMC-LOGI-VEN001'
            
            # Prepare vendor data
            vendor_data = {
                'vendor_id': vendor_id,
                'organization_name': request.form.get('organization_name'),
                'organization_type': request.form.get('organization_type'),
                'contact_number': request.form.get('contact_number'),
                'email_id': request.form.get('email_id'),
                'website': request.form.get('website'),
                'address': request.form.get('address'),
                'phone_number': request.form.get('phone_number'),
                'type_of_purchase': ', '.join(request.form.getlist('type_of_purchase')),  # Get multiple selections
                'date_of_vendorship': request.form.get('date_of_vendorship') or None,
                'description': request.form.get('description'),
                'approval_status': 'pending',
                'status': 'active',
                'created_by': session.get('admin')
            }
            
            # Insert into database
            response = supabase.table('vendors').insert(vendor_data).execute()
            
            if response.data:
                flash(f'Vendor {vendor_id} added successfully!', 'success')
                return redirect(url_for('admin_add_vendor', success='true', vendor_id=vendor_id))
            else:
                flash('Error adding vendor. Please try again.', 'danger')
        
        except Exception as e:
            print(f"Error adding vendor: {e}")
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('admin_add_vendor.html')

@app.route('/admin/vendors/<path:vendor_id>/view')
@admin_required
def admin_view_vendor(vendor_id):
    """View vendor details"""
    try:
        response = supabase.table('vendors').select('*').eq('vendor_id', vendor_id).execute()
        
        if response.data and len(response.data) > 0:
            vendor = response.data[0]
            return render_template('admin_view_vendor.html', vendor=vendor)
        else:
            flash('Vendor not found', 'danger')
            return redirect(url_for('admin_vendors'))
    except Exception as e:
        print(f"Error loading vendor: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin_vendors'))

@app.route('/admin/vendors/<path:vendor_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_vendor(vendor_id):
    """Edit vendor details"""
    try:
        if request.method == 'POST':
            update_data = {
                'organization_name': request.form.get('organization_name'),
                'organization_type': request.form.get('organization_type'),
                'contact_number': request.form.get('contact_number'),
                'email_id': request.form.get('email_id'),
                'website': request.form.get('website'),
                'address': request.form.get('address'),
                'phone_number': request.form.get('phone_number'),
                'type_of_purchase': ', '.join(request.form.getlist('type_of_purchase')),  # Get multiple selections
                'date_of_vendorship': request.form.get('date_of_vendorship') or None,
                'description': request.form.get('description'),
                'status': request.form.get('status', 'active')
            }
            
            response = supabase.table('vendors').update(update_data).eq('vendor_id', vendor_id).execute()
            
            if response.data:
                flash(f'Vendor {vendor_id} updated successfully!', 'success')
                return redirect(url_for('admin_view_vendor', vendor_id=vendor_id))
            else:
                flash('Error updating vendor. Please try again.', 'danger')
        
        # GET request - load vendor data
        response = supabase.table('vendors').select('*').eq('vendor_id', vendor_id).execute()
        
        if response.data and len(response.data) > 0:
            vendor = response.data[0]
            return render_template('admin_edit_vendor.html', vendor=vendor)
        else:
            flash('Vendor not found', 'danger')
            return redirect(url_for('admin_vendors'))
            
    except Exception as e:
        print(f"Error editing vendor: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin_vendors'))

@app.route('/admin/vendors/<path:vendor_id>/approve', methods=['POST'])
@admin_required
def admin_approve_vendor(vendor_id):
    """Approve vendor"""
    try:
        from datetime import datetime
        
        update_data = {
            'approval_status': 'approved',
            'approved_by': session.get('admin'),
            'approved_date': datetime.now().isoformat()
        }
        
        response = supabase.table('vendors').update(update_data).eq('vendor_id', vendor_id).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Vendor approved successfully'})
        else:
            return jsonify({'success': False, 'message': 'Error approving vendor'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ===== PAYMENT MANAGEMENT ROUTES =====
@app.route('/admin/payments')
@admin_required
def admin_payments():
    """Display all payments with statistics"""
    try:
        # Get all payments
        response = supabase.table('payments').select('*').order('created_at', desc=True).execute()
        payments = response.data if response.data else []
        
        # Add payment_status for vouchers and fetch associated invoice items
        for payment in payments:
            payment['invoices'] = []  # Initialize invoices list
            
            if payment.get('payment_type') == 'payment_voucher':
                inv_no = payment['invoice_no']
                payable = payment.get('total_payable', 0)
                paid_resp = supabase.table('payments').select('amount').eq('payment_type', 'payment_details').eq('voucher_entry_no', payment.get('entry_no')).execute()
                total_paid = sum(float(p.get('amount', 0)) for p in paid_resp.data or [])
                payment['payment_status'] = 'paid' if total_paid >= payable else 'pending'
                
                # Fetch associated invoice items for this payment voucher
                try:
                    voucher_items = supabase.table('payment_voucher_items').select('invoice_no').eq('payment_entry_no', payment.get('entry_no')).execute()
                    # Get unique invoice numbers
                    invoices = list(set([item.get('invoice_no') for item in (voucher_items.data or []) if item.get('invoice_no')]))
                    payment['invoices'] = invoices
                except:
                    payment['invoices'] = []
                    
            elif payment.get('payment_type') == 'payment_details':
                # For payment_details, fetch invoices from the linked voucher
                voucher_entry_no = payment.get('voucher_entry_no')
                if voucher_entry_no:
                    try:
                        voucher_items = supabase.table('payment_voucher_items').select('invoice_no').eq('payment_entry_no', voucher_entry_no).execute()
                        # Get unique invoice numbers
                        invoices = list(set([item.get('invoice_no') for item in (voucher_items.data or []) if item.get('invoice_no')]))
                        payment['invoices'] = invoices
                    except:
                        payment['invoices'] = []
                payment['payment_status'] = 'N/A'
            else:
                payment['payment_status'] = 'N/A'
        
        # Calculate statistics
        total_payments = len(payments)
        approved_payments = sum(1 for p in payments if p.get('approval_status') == 'approved')
        pending_payments = sum(1 for p in payments if p.get('approval_status') == 'pending')
        total_amount = sum(float(p.get('amount', 0)) for p in payments if p.get('approval_status') == 'approved')
        
        return render_template('admin_payments.html',
                             payments=payments,
                             total_payments=total_payments,
                             approved_payments=approved_payments,
                             pending_payments=pending_payments,
                             total_amount=f"{total_amount:,.2f}")
    except Exception as e:
        print(f"Error loading payments: {e}")
        flash(f'Error loading payments: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/payments/add', methods=['GET', 'POST'])
@admin_required
def admin_add_payment():
    """Add new payment"""
    try:
        if request.method == 'POST':
            from datetime import datetime
            
            payment_data = {
                'invoice_no': request.form.get('invoice_no'),
                'vendor_id': request.form.get('vendor_id'),
                'value': float(request.form.get('value', 0)),
                'dn': request.form.get('dn'),
                'type_of_entry': request.form.get('type_of_entry'),
                'mode_of_payment': request.form.get('mode_of_payment'),
                'payment_advice': request.form.get('payment_advice'),
                'payment_date': request.form.get('payment_date') or None,
                'amount': float(request.form.get('amount', 0)),
                'entered_by': session.get('admin'),
                'approval_status': 'pending',
                'status': 'active'
            }
            
            # Try to use RPC function for auto-generated entry_no, with fallback
            try:
                result = supabase.rpc('get_next_payment_entry_no').execute()
                if result.data:
                    payment_data['entry_no'] = result.data
            except:
                # Fallback: generate entry_no manually
                response = supabase.table('payments').select('entry_no').order('created_at', desc=True).limit(1).execute()
                if response.data and len(response.data) > 0:
                    last_entry = response.data[0].get('entry_no', '')
                    import re
                    match = re.search(r'PAY(\d+)', last_entry)
                    if match:
                        num = int(match.group(1)) + 1
                    else:
                        num = 1
                else:
                    num = 1
                payment_data['entry_no'] = f'PMCTECH-LOGI-PAY{str(num).zfill(4)}'
            
            response = supabase.table('payments').insert(payment_data).execute()
            
            if response.data:
                entry_no = response.data[0].get('entry_no')
                flash(f'Payment {entry_no} created successfully!', 'success')
                return redirect(url_for('admin_payments'))
            else:
                flash('Error creating payment. Please try again.', 'danger')
        
        # Fetch all purchases with invoice numbers and vendors
        purchases_response = supabase.table('purchases').select('invoice_no, vendor, total_payment, invoice_date').order('invoice_no').execute()
        purchases_data = purchases_response.data if purchases_response.data else []
        
        # Group by invoice_no and calculate totals
        invoice_dict = {}
        for purchase in purchases_data:
            inv_no = purchase.get('invoice_no')
            if inv_no:
                if inv_no not in invoice_dict:
                    invoice_dict[inv_no] = {
                        'invoice_no': inv_no,
                        'vendor': purchase.get('vendor'),
                        'invoice_date': purchase.get('invoice_date'),
                        'total_value': 0
                    }
                invoice_dict[inv_no]['total_value'] += float(purchase.get('total_payment', 0))
        
        invoices_list = list(invoice_dict.values())
        
        return render_template('admin_add_payment.html', invoices=invoices_list)
        
    except Exception as e:
        print(f"Error adding payment: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin_payments'))

@app.route('/admin/payments/<entry_no>/approve', methods=['POST'])
@admin_required
def admin_approve_payment(entry_no):
    """Approve payment"""
    try:
        from datetime import datetime
        
        update_data = {
            'approval_status': 'approved',
            'approved_by': session.get('admin'),
            'approved_date': datetime.now().isoformat()
        }
        
        response = supabase.table('payments').update(update_data).eq('entry_no', entry_no).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Payment approved successfully'})
        else:
            return jsonify({'success': False, 'message': 'Error approving payment'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/payment-voucher/get-next-ref', methods=['GET'])
@admin_required
def get_next_ref_number():
    """Get next reference number based on institution type"""
    try:
        institution_type = request.args.get('institution_type', 'Engineering')
        institution_code = 'ENGG' if institution_type == 'Engineering' else 'POLY'
        
        # Try to use RPC function first
        try:
            result = supabase.rpc('get_next_ref_number', {'p_institution_type': institution_type}).execute()
            if result.data:
                return jsonify({'success': True, 'ref_number': result.data})
        except:
            pass
        
        # Fallback: generate ref_number manually with VOC- prefix
        response = supabase.table('payments').select('ref_number').like('ref_number', f'PMC-{institution_code}-LOGI-VOC-%').order('created_at', desc=True).limit(1).execute()
        
        if response.data and len(response.data) > 0:
            last_ref = response.data[0].get('ref_number', '')
            import re
            match = re.search(r'VOC-(\d+)', last_ref)
            if match:
                num = int(match.group(1)) + 1
            else:
                num = 1
        else:
            num = 1
        
        ref_number = f'PMC-{institution_code}-LOGI-VOC-{str(num).zfill(4)}'
        return jsonify({'success': True, 'ref_number': ref_number})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/payment-voucher', methods=['GET', 'POST'])
@admin_required
def admin_add_payment_voucher():
    """Add new payment voucher"""
    try:
        if request.method == 'POST':
            from datetime import datetime
            
            institution_type = request.form.get('institution_type', 'Engineering')
            
            # Capture all invoice numbers from the multi-invoice form
            invoice_nos_list = request.form.getlist('invoice_no_row[]')
            # Remove duplicates and empty values, then join with comma
            unique_invoices = list(set([inv for inv in invoice_nos_list if inv]))
            invoice_nos_str = ','.join(unique_invoices) if unique_invoices else ''
            
            payment_data = {
                'invoice_no': invoice_nos_str,  # Store as comma-separated string
                'vendor_id': request.form.get('vendor_id'),
                'value': float(request.form.get('value', 0)),
                'dn': request.form.get('dn'),
                'type_of_entry': 'payment_voucher',
                'mode_of_payment': request.form.get('mode_of_payment'),
                'payment_advice': request.form.get('payment_advice'),
                'payment_date': request.form.get('payment_date') or None,
                'amount': float(request.form.get('amount', 0)),
                'entered_by': session.get('admin'),
                'approval_status': 'pending',
                'status': 'active',
                'payment_type': 'payment_voucher',
                'institution_type': institution_type,
                'total_parts': float(request.form.get('total_parts', 0)),
                'total_labour': float(request.form.get('total_labour', 0)),
                'total_taxable': float(request.form.get('total_taxable', 0)),
                'total_gst': float(request.form.get('total_gst', 0)),
                'total_dn': float(request.form.get('total_dn', 0)),
                'total_payable': float(request.form.get('total_payable', 0))
            }
            
            # Generate reference number based on institution type
            try:
                result = supabase.rpc('get_next_ref_number', {'p_institution_type': institution_type}).execute()
                if result.data:
                    payment_data['ref_number'] = result.data
            except:
                # Fallback: generate ref_number manually with VOC- prefix
                institution_code = 'ENGG' if institution_type == 'Engineering' else 'POLY'
                response = supabase.table('payments').select('ref_number').like('ref_number', f'PMC-{institution_code}-LOGI-VOC-%').order('created_at', desc=True).limit(1).execute()
                if response.data and len(response.data) > 0:
                    last_ref = response.data[0].get('ref_number', '')
                    import re
                    match = re.search(r'VOC-(\d+)', last_ref)
                    if match:
                        num = int(match.group(1)) + 1
                    else:
                        num = 1
                else:
                    num = 1
                payment_data['ref_number'] = f'PMC-{institution_code}-LOGI-VOC-{str(num).zfill(4)}'
            
            # Try to use RPC function for auto-generated entry_no, with fallback
            try:
                result = supabase.rpc('get_next_payment_entry_no').execute()
                if result.data:
                    payment_data['entry_no'] = result.data
            except:
                # Fallback: generate entry_no manually
                response = supabase.table('payments').select('entry_no').order('created_at', desc=True).limit(1).execute()
                if response.data and len(response.data) > 0:
                    last_entry = response.data[0].get('entry_no', '')
                    import re
                    match = re.search(r'PAY(\d+)', last_entry)
                    if match:
                        num = int(match.group(1)) + 1
                    else:
                        num = 1
                else:
                    num = 1
                payment_data['entry_no'] = f'PMCTECH-LOGI-PAY{str(num).zfill(4)}'
            
            response = supabase.table('payments').insert(payment_data).execute()
            
            if response.data:
                entry_no = response.data[0].get('entry_no')
                
                # Insert voucher items - now with correct invoice numbers per row
                parts_prices = request.form.getlist('parts_price[]')
                labour_charges = request.form.getlist('labour_charge[]')
                gst_amounts = request.form.getlist('gst_amount[]')
                dn_amounts = request.form.getlist('dn_amount[]')
                taxable_amounts = request.form.getlist('taxable_amount[]')
                payable_amounts = request.form.getlist('payable_amount[]')
                work_descriptions = request.form.getlist('work_description[]')
                bus_reg_nos = request.form.getlist('bus_reg_no[]')
                invoice_nos = request.form.getlist('invoice_no_row[]')  # Get individual invoice numbers per row
                
                for i in range(len(parts_prices)):
                    item_data = {
                        'payment_entry_no': entry_no,
                        'line_number': i + 1,
                        'invoice_no': invoice_nos[i] if i < len(invoice_nos) else '',  # Use invoice number from this row
                        'bus_reg_no': bus_reg_nos[i] if i < len(bus_reg_nos) else '',
                        'work_description': work_descriptions[i] if i < len(work_descriptions) else '',
                        'parts_price': float(parts_prices[i] or 0),
                        'labour_charge': float(labour_charges[i] or 0),
                        'taxable_amount': float(taxable_amounts[i] or 0),
                        'gst_amount': float(gst_amounts[i] or 0),
                        'dn_amount': float(dn_amounts[i] or 0),
                        'payable_amount': float(payable_amounts[i] or 0)
                    }
                    supabase.table('payment_voucher_items').insert(item_data).execute()
                
                flash(f'Payment Voucher {entry_no} created successfully!', 'success')
                return redirect(url_for('admin_payments'))
            else:
                flash('Error creating payment voucher. Please try again.', 'danger')
        
        # Fetch all purchases with invoice numbers and vendors
        purchases_response = supabase.table('purchases').select('invoice_no, vendor, total_payment, invoice_date').order('invoice_no').execute()
        purchases_data = purchases_response.data if purchases_response.data else []
        
        # Group by invoice_no and calculate totals
        invoice_dict = {}
        for purchase in purchases_data:
            inv_no = purchase.get('invoice_no')
            if inv_no:
                if inv_no not in invoice_dict:
                    invoice_dict[inv_no] = {
                        'invoice_no': inv_no,
                        'vendor': purchase.get('vendor'),
                        'invoice_date': purchase.get('invoice_date'),
                        'total_value': 0
                    }
                invoice_dict[inv_no]['total_value'] += float(purchase.get('total_payment', 0))
        
        invoices_list = list(invoice_dict.values())
        
        # Fetch invoice numbers that have payment vouchers
        voucher_response = supabase.table('payment_voucher_items').select('invoice_no').execute()
        voucher_invoices = set([item['invoice_no'] for item in voucher_response.data if item['invoice_no']]) if voucher_response.data else set()
        
        # Filter out invoices that already have vouchers
        invoices_list = [inv for inv in invoices_list if inv['invoice_no'] not in voucher_invoices]
        
        return render_template('admin_add_payment_voucher.html', invoices=invoices_list)
        
    except Exception as e:
        print(f"Error adding payment voucher: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin_payments'))

@app.route('/admin/payment-details', methods=['GET', 'POST'])
@admin_required
def admin_add_payment_details():
    """Add new payment details for payment vouchers"""
    try:
        if request.method == 'POST':
            from datetime import datetime
            
            # Get the selected voucher details
            voucher_entry_no = request.form.get('voucher_entry_no')
            voucher_ref_number = request.form.get('voucher_ref_number')
            institution_type = request.form.get('institution_type', 'Engineering')
            
            # Normalize institution_type to match check constraint (Engineering or Polytechnic)
            if 'poly' in institution_type.lower():
                institution_type = 'Polytechnic'
            else:
                institution_type = 'Engineering'
            
            payment_data = {
                'voucher_entry_no': voucher_entry_no,  # Link to the voucher
                'ref_number': voucher_ref_number,  # Store voucher ref number for reference
                'institution_type': institution_type,  # Store the institution type
                'type_of_entry': request.form.get('type_of_entry'),
                'mode_of_payment': request.form.get('mode_of_payment'),
                'payment_advice': request.form.get('payment_advice'),
                'payment_date': request.form.get('payment_date') or None,
                'amount': float(request.form.get('amount', 0)),
                'entered_by': session.get('admin'),
                'approval_status': request.form.get('approval_status', 'pending'),
                'status': 'active',
                'payment_type': 'payment_details',
                # Payment method specific reference numbers
                'cheque_number': request.form.get('cheque_number') or None,
                'utr_number': request.form.get('utr_number') or None,
                'neft_rtgs_number': request.form.get('neft_rtgs_number') or None,
                'draft_number': request.form.get('draft_number') or None,
                'card_number': request.form.get('card_number') or None
            }
            
            # Try to use RPC function to generate PAID entry_no based on institution type
            try:
                result = supabase.rpc('get_next_paid_entry_no', {'p_institution_type': institution_type}).execute()
                if result.data:
                    payment_data['entry_no'] = result.data
            except Exception as e:
                # Fallback: generate entry_no manually
                import re
                prefix = 'PMC-POLY-LOGI-PAID' if institution_type == 'Polytechnic' else 'PMC-ENGG-LOGI-PAID'
                response = supabase.table('payments').select('entry_no').eq('payment_type', 'payment_details').like('entry_no', f'{prefix}-%').order('entry_no', desc=True).limit(1).execute()
                
                v_last_num = 0
                if response.data and len(response.data) > 0:
                    last_entry = response.data[0].get('entry_no', '')
                    match = re.search(r'-(\d+)$', last_entry)
                    if match:
                        v_last_num = int(match.group(1))
                
                v_new_num = v_last_num + 1
                payment_data['entry_no'] = f'{prefix}-{str(v_new_num).zfill(4)}'
            
            response = supabase.table('payments').insert(payment_data).execute()
            
            if response.data:
                entry_no = response.data[0].get('entry_no')
                flash(f'Payment recorded {entry_no} for voucher {voucher_ref_number}!', 'success')
                return redirect(url_for('admin_payments'))
            else:
                flash('Error recording payment. Please try again.', 'danger')
        
        # Fetch all payment vouchers that haven't been fully paid
        vouchers_response = supabase.table('payments').select('entry_no, ref_number, institution_type, total_payable').eq('payment_type', 'payment_voucher').execute()
        vouchers_list = []
        
        if vouchers_response.data:
            for voucher in vouchers_response.data:
                entry_no = voucher.get('entry_no')
                ref_number = voucher.get('ref_number')
                total_payable = float(voucher.get('total_payable', 0))
                
                # Fetch payment details already recorded for this voucher
                paid_response = supabase.table('payments').select('amount').eq('payment_type', 'payment_details').eq('voucher_entry_no', entry_no).execute()
                paid_amount = sum(float(p.get('amount', 0)) for p in (paid_response.data or []))
                
                # Only show vouchers that haven't been fully paid
                remaining = total_payable - paid_amount
                if remaining > 0:
                    vouchers_list.append({
                        'entry_no': entry_no,
                        'ref_number': ref_number,
                        'institution_type': voucher.get('institution_type', 'Engineering'),
                        'total_payable': total_payable,
                        'paid_amount': paid_amount,
                        'remaining': remaining
                    })
        
        return render_template('admin_add_payment_details.html', vouchers=vouchers_list)
        
    except Exception as e:
        print(f"Error adding paid details: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin_payments'))

@app.route('/admin/payments/<entry_no>/view', methods=['GET'])
@admin_required
def admin_view_payment(entry_no):
    """View payment details"""
    try:
        # Fetch payment record
        payment_response = supabase.table('payments').select('*').eq('entry_no', entry_no).single().execute()
        payment = payment_response.data
        
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('admin_payments'))
        
        # If it's a voucher, fetch line items
        line_items = []
        if payment.get('payment_type') == 'payment_voucher':
            items_response = supabase.table('payment_voucher_items').select('*').eq('payment_entry_no', entry_no).order('line_number').execute()
            line_items = items_response.data if items_response.data else []
        
        return render_template('admin_view_payment.html', payment=payment, line_items=line_items)
        
    except Exception as e:
        print(f"Error viewing payment: {e}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin_payments'))

@app.route('/admin/purchases/invoice/<invoice_no>', methods=['GET'])
@admin_required
def admin_get_purchases_by_invoice(invoice_no):
    """Return purchase line items for a given invoice number."""
    try:
        response = supabase.table('purchases').select(
            'invoice_no, part_name, quantity, rate, taxable_amount, '
            'sgst_amount, cgst_amount, igst_amount, total_payment'
        ).eq('invoice_no', invoice_no).order('created_at').execute()

        items = []
        for row in response.data or []:
            quantity = float(row.get('quantity') or 0)
            rate = float(row.get('rate') or 0)
            parts_price = quantity * rate
            taxable_amount = float(row.get('taxable_amount') or 0)
            if parts_price == 0 and taxable_amount:
                parts_price = taxable_amount
            gst_amount = float(row.get('sgst_amount') or 0) + float(row.get('cgst_amount') or 0) + float(row.get('igst_amount') or 0)
            payable_amount = float(row.get('total_payment') or (taxable_amount + gst_amount))

            items.append({
                'invoice_no': row.get('invoice_no'),
                'part_or_work_name': row.get('part_name') or '',
                'parts_price': round(parts_price, 2),
                'labour_charge': 0,
                'taxable_amount': round(taxable_amount, 2),
                'gst_amount': round(gst_amount, 2),
                'payable_amount': round(payable_amount, 2),
                'bus_reg_no': ''
            })

        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'items': []})


@app.route('/api/internal_audit', methods=['POST'])
@login_required
def api_internal_audit():
    """Receive internal audit payload from client and persist to Supabase.
    This endpoint is intentionally simple: it accepts JSON and attempts to
    insert into an `internal_audits` table if available. It always returns
    JSON with success status and diagnostic info for debugging.
    """
    try:
        data = request.get_json(force=True)
        app.logger.debug('Received internal_audit payload: %s', data)
        # Attempt to insert into Supabase table `internal_audits` if present
        try:
            # Clean and coerce incoming payload to match expected DB column types.
            payload = {}
            payload['audit_date'] = data.get('audit_date')
            # Normalize month: accept 'February' or '2' -> store integer where DB expects smallint
            month_val = data.get('month')
            month_num = None
            if month_val is not None:
                try:
                    month_num = int(month_val)
                except Exception:
                    try:
                        # parse full month name like 'February'
                        month_num = datetime.strptime(str(month_val), '%B').month
                    except Exception:
                        try:
                            # parse abbreviated month like 'Feb'
                            month_num = datetime.strptime(str(month_val), '%b').month
                        except Exception:
                            month_num = None
            # If we could parse month to integer, use that. If not, send NULL
            # (avoids inserting string like 'February' into a smallint column)
            payload['month'] = month_num if month_num is not None else None

            payload['auditor_1'] = data.get('auditor_1')
            payload['auditor_2'] = data.get('auditor_2')
            payload['auditee'] = data.get('auditee')
            # also store optional name / designation fields if provided
            payload['auditor_1_name'] = data.get('auditor_1_name') or data.get('auditor1_name') or data.get('auditor1')
            payload['auditor_1_designation'] = data.get('auditor_1_designation') or data.get('auditor1_designation') or data.get('auditor1_desig')
            payload['auditor_2_name'] = data.get('auditor_2_name') or data.get('auditor2_name') or data.get('auditor2')
            payload['auditor_2_designation'] = data.get('auditor_2_designation') or data.get('auditor2_designation') or data.get('auditor2_desig')
            payload['auditee_name'] = data.get('auditee_name') or data.get('auditeeName') or data.get('auditee_fullname')
            payload['auditee_designation'] = data.get('auditee_designation') or data.get('auditee_desig')
            payload['vehicle_id'] = data.get('vehicle_id')
            payload['registration_no'] = data.get('registration_no')
            # km_reading -> integer
            try:
                payload['km_reading'] = int(data.get('km_reading')) if data.get('km_reading') not in (None, '') else None
            except Exception:
                payload['km_reading'] = None
            # ratings as JSONB (keep as list/dict)
            payload['ratings'] = data.get('ratings')
            # overall fields as integers
            try:
                payload['overall_rating'] = int(data.get('overall_rating'))
            except Exception:
                payload['overall_rating'] = None
            try:
                payload['overall_percent'] = int(data.get('overall_percent'))
            except Exception:
                payload['overall_percent'] = None
            # created_at
            payload['created_at'] = data.get('created_at') or datetime.utcnow().isoformat()

            res = supabase.table('internal_audits').insert(payload).execute()
            return jsonify({'success': True, 'message': 'Inserted', 'result': res.data}), 201
        except Exception as e:
            # Log the exception, then attempt to persist payload locally as a fallback
            app.logger.exception('Failed to insert internal_audits')
            fallback_path = os.path.join(os.getcwd(), 'internal_audits_fallback.jsonl')
            try:
                        with open(fallback_path, 'a', encoding='utf-8') as fh:
                            import json
                            entry = {'error': str(e), 'payload': data, 'ts': datetime.utcnow().isoformat()}
                            fh.write(json.dumps(entry) + "\n")
                        # Return the saved payload so client can show it immediately if desired
                        return jsonify({'success': True, 'message': 'saved_local', 'saved_path': fallback_path, 'insert_error': str(e), 'saved_payload': data, 'saved_ts': entry['ts']}), 201
            except Exception as fe:
                app.logger.exception('Failed to write fallback audit file')
                return jsonify({'success': False, 'message': 'Failed to insert and failed to save locally', 'insert_error': str(e), 'file_error': str(fe)}), 500
    except Exception as e:
        app.logger.exception('Bad request for internal_audit')
        return jsonify({'success': False, 'message': str(e)}), 400

try:
    # Start background reminders scheduler if available. This will schedule
    # daily checks for vehicle validity dates and send emails when configured.
    from reminders import start_scheduler
    start_scheduler(app)
except Exception:
    # Don't fail app startup if scheduler cannot be started
    try:
        app.logger.exception('Could not start reminders scheduler')
    except Exception:
        pass

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


# Simple health endpoint for debugging deploy/Supabase connectivity
@app.route('/_health')
def _health():
    result = {'status': 'ok'}
    # package versions
    try:
        try:
            from importlib import metadata
        except Exception:
            import importlib_metadata as metadata
        result['packages'] = {
            'supabase': metadata.version('supabase') if metadata.version('supabase') else '(n/a)',
            'httpx': metadata.version('httpx') if metadata.version('httpx') else '(n/a)',
            'gotrue': metadata.version('gotrue') if metadata.version('gotrue') else '(n/a)'
        }
    except Exception as e:
        result['packages'] = {'error': str(e)}

    # Supabase connectivity check (safe - does not return secrets)
    try:
        resp = None
        try:
            resp = supabase.table('users').select('id,email').limit(1).execute()
        except Exception as e:
            result['supabase_error'] = str(e)
        else:
            result['supabase_rows'] = len(resp.data) if getattr(resp, 'data', None) is not None else 0
    except Exception as e:
        result['supabase_error'] = str(e)

    return jsonify(result)
