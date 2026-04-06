import os
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from flask import current_app

load_dotenv()

# Lazy-initialize Supabase client to avoid failing at import-time on incompatible
# runtime environments (helps when Render is still using an unexpected Python)
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

# Optional local development fallback: if USE_MOCK_DB is set to a truthy value
# we delegate authentication/logging helpers to `database_mock.py` so the
# app can run and accept test logins without contacting Supabase.
use_mock_db = os.getenv("USE_MOCK_DB", "").lower() in ("1", "true", "yes")
if use_mock_db:
    try:
        import database_mock as _dbm
        print("USING MOCK DATABASE (USE_MOCK_DB=true) - auth calls delegated to database_mock")
        authenticate_user = _dbm.authenticate_user
        authenticate_super_admin = _dbm.authenticate_super_admin
        log_login_attempt = _dbm.log_login_attempt
        create_user = _dbm.create_user
        create_super_admin = _dbm.create_super_admin
        get_all_users = _dbm.get_all_users
        update_user_status = _dbm.update_user_status
    except Exception as e:
        print(f"Failed to enable mock DB: {e}")

def _get_installed_version(pkg_name: str) -> str:
    try:
        try:
            from importlib import metadata
        except Exception:
            import importlib_metadata as metadata
        return metadata.version(pkg_name)
    except Exception:
        return "(not installed)"

def _init_supabase():
    # print versions to logs for easier debugging on deploy
    try:
        print(f"Dependencies: supabase={_get_installed_version('supabase')} httpx={_get_installed_version('httpx')} gotrue={_get_installed_version('gotrue')}")
    except Exception:
        pass

    if not url or not key:
        print("WARNING: SUPABASE_URL or SUPABASE_KEY not set. Supabase client will not be initialized until env vars are provided.")
        return None

    try:
        return create_client(url, key)
    except Exception as e:
        print(f"Supabase initialization error: {e}")
        return None

_supabase_client = None

class _SupabaseProxy:
    def __getattr__(self, name):
        global _supabase_client
        if _supabase_client is None:
            _supabase_client = _init_supabase()
        if _supabase_client is None:
            raise RuntimeError("Supabase client is not available. Check SUPABASE_URL/SUPABASE_KEY and dependency compatibility.")
        return getattr(_supabase_client, name)

# Export a proxy object named `supabase` so existing code can continue using
# `supabase.table(...)` etc. The real client will be created on first use.
supabase = _SupabaseProxy()

# Helper to enable the local mock DB (used for development when Supabase is
# unreachable). We assign auth/logging convenience functions from
# `database_mock` so the rest of the app keeps calling the same symbols.
def _enable_mock_db():
    try:
        import database_mock as _dbm
        print("USING MOCK DATABASE (auto-enabled) - auth calls delegated to database_mock")
        globals()['authenticate_user'] = _dbm.authenticate_user
        globals()['authenticate_super_admin'] = _dbm.authenticate_super_admin
        globals()['log_login_attempt'] = _dbm.log_login_attempt
        globals()['create_user'] = _dbm.create_user
        globals()['create_super_admin'] = _dbm.create_super_admin
        globals()['get_all_users'] = _dbm.get_all_users
        globals()['update_user_status'] = _dbm.update_user_status
        return True
    except Exception as e:
        print(f"Failed to enable mock DB: {e}")
        return False

# If the user explicitly requested mock DB via env, we've already wired it above.
# Otherwise, attempt to initialize Supabase if credentials are present. If
# initialization fails, fail fast with a clear diagnostic so the developer can
# either fix credentials or explicitly opt into the mock DB using
# `USE_MOCK_DB=true`. This avoids silently switching behavior at runtime.
if not use_mock_db:
    if url and key:
        try:
            _supabase_client = _init_supabase()
        except Exception:
            _supabase_client = None

        if _supabase_client is None:
            print("ERROR: Supabase client could not be initialized with the provided SUPABASE_URL/SUPABASE_KEY.")
            print("To run without Supabase, set USE_MOCK_DB=true in your .env or environment and restart the app.")
            print("Aborting startup to avoid unexpected mock fallback.")
            try:
                import sys
                sys.exit(1)
            except Exception:
                raise RuntimeError("Supabase initialization failed and mock DB not enabled.")

def authenticate_user(email, password):
    """Authenticate a regular user"""
    try:
        # Query users table with case-insensitive email
        email_lower = email.lower().strip()
        try:
            response = supabase.table('users').select('*').eq('email', email_lower).eq('is_active', True).execute()
        except Exception as e:
            print(f"Authentication error: {e}")
            # If Supabase is unreachable, fall back to local mock DB if available
            try:
                import database_mock as _dbm
                print("Falling back to database_mock.authenticate_user due to Supabase error")
                return _dbm.authenticate_user(email_lower, password)
            except Exception:
                raise
        
        # Fallback: if no match, try case-insensitive via fetch and filter (if DB doesn't support ilike)
        if not response.data or len(response.data) == 0:
            all_users = supabase.table('users').select('*').eq('is_active', True).execute()
            for user in (all_users.data or []):
                if user.get('email', '').lower().strip() == email_lower:
                    response.data = [user]
                    break
        
        if response.data and len(response.data) > 0:
            user = response.data[0]
            stored_pw = user.get('password') or ''
            print(f"[DEBUG] Auth: attempting login for {email_lower}, stored pw starts with: {stored_pw[:10] if stored_pw else '(empty)'}")
            
            try:
                # Try bcrypt (most common for hashed passwords)
                if stored_pw.startswith('$2b$') or stored_pw.startswith('$2a$'):
                    import bcrypt
                    if bcrypt.checkpw(password.encode('utf-8'), stored_pw.encode('utf-8')):
                        print(f"[DEBUG] Auth: bcrypt match for {email_lower}")
                        return user
                # Try Werkzeug hash (pbkdf2, sha256, etc)
                elif stored_pw.startswith('pbkdf2:') or stored_pw.startswith('sha256:') or ':' in stored_pw or '$' in stored_pw:
                    if check_password_hash(stored_pw, password):
                        print(f"[DEBUG] Auth: werkzeug hash match for {email_lower}")
                        return user
                # Plain text fallback
                else:
                    if stored_pw == password:
                        print(f"[DEBUG] Auth: plaintext match for {email_lower}")
                        return user
            except Exception as e:
                print(f"[DEBUG] Auth: hash check error for {email_lower}: {e}, trying plaintext fallback")
                if stored_pw == password:
                    return user
        
        print(f"[DEBUG] Auth: no match or user not found for {email_lower}")
        return None
    except Exception as e:
        print(f"Authentication error: {e}")
        import traceback
        traceback.print_exc()
        return None

def authenticate_super_admin(identifier, password):
    """Authenticate a super admin user by email or username"""
    try:
        password = password.strip()
        identifier_lower = identifier.lower().strip()
        
        # Try to find admin by email first (case-insensitive)
        try:
            response = supabase.table('super_admins').select('*').eq('email', identifier_lower).eq('is_active', True).execute()
        except Exception as e:
            print(f"Admin authentication error: {e}")
            try:
                import database_mock as _dbm
                print("Falling back to database_mock.authenticate_super_admin due to Supabase error")
                return _dbm.authenticate_super_admin(identifier_lower, password)
            except Exception:
                raise
        
        # If not found by email, try username (case-insensitive)
        if not response.data or len(response.data) == 0:
            response = supabase.table('super_admins').select('*').eq('username', identifier_lower).eq('is_active', True).execute()
        
        # Fallback: fetch all and filter case-insensitively
        if not response.data or len(response.data) == 0:
            all_admins = supabase.table('super_admins').select('*').eq('is_active', True).execute()
            for admin in (all_admins.data or []):
                if admin.get('email', '').lower().strip() == identifier_lower or admin.get('username', '').lower().strip() == identifier_lower:
                    response.data = [admin]
                    break
        
        if response.data and len(response.data) > 0:
            admin = response.data[0]
            stored_pw = admin.get('password') or ''
            print(f"[DEBUG] Admin auth: attempting login for {identifier_lower}, stored pw starts with: {stored_pw[:10] if stored_pw else '(empty)'}")
            
            try:
                # Try bcrypt
                if stored_pw.startswith('$2b$') or stored_pw.startswith('$2a$'):
                    import bcrypt
                    if bcrypt.checkpw(password.encode('utf-8'), stored_pw.encode('utf-8')):
                        print(f"[DEBUG] Admin auth: bcrypt match for {identifier_lower}")
                        return admin
                # Try Werkzeug hash
                elif stored_pw.startswith('pbkdf2:') or stored_pw.startswith('sha256:') or ':' in stored_pw or '$' in stored_pw:
                    if check_password_hash(stored_pw, password):
                        print(f"[DEBUG] Admin auth: werkzeug hash match for {identifier_lower}")
                        return admin
                # Plain text fallback
                else:
                    if stored_pw.strip() == password:
                        print(f"[DEBUG] Admin auth: plaintext match for {identifier_lower}")
                        return admin
            except Exception as e:
                print(f"[DEBUG] Admin auth: hash check error for {identifier_lower}: {e}, trying plaintext fallback")
                if stored_pw.strip() == password:
                    return admin
        
        print(f"[DEBUG] Admin auth: no match or admin not found for {identifier_lower}")
        return None
    except Exception as e:
        print(f"Admin authentication error: {e}")
        import traceback
        traceback.print_exc()
        return None

def log_login_attempt(identifier, success, ip_address):
    """Log login attempts"""
    try:
        supabase.table('login_logs').insert({
            'user_identifier': identifier,
            'success': success,
            'ip_address': ip_address,
            'timestamp': datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"Error logging login attempt: {e}")

def create_user(email, password, full_name, role='user'):
    """Create a new user"""
    try:
        response = supabase.table('users').insert({
            'email': email,
            'password': password,
            'full_name': full_name,
            'role': role,
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def create_super_admin(username, password, full_name):
    """Create a new super admin"""
    try:
        response = supabase.table('super_admins').insert({
            'username': username,
            'password': password,
            'full_name': full_name,
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating super admin: {e}")
        return None

def get_all_users():
    """Get all users"""
    try:
        response = supabase.table('users').select('*').execute()
        return response.data
    except Exception as e:
        print(f"Error getting users: {e}")
        return []

def update_user_status(user_id, is_active):
    """Update user active status"""
    try:
        response = supabase.table('users').update({'is_active': is_active}).eq('id', user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating user status: {e}")
        return None

def save_vehicle_annual_record(vehicle_data):
    """Save or update vehicle annual record"""
    try:
        # Check if record exists for this vehicle
        vehicle_id = vehicle_data.get('vehicle_id')
        
        # Convert None values to empty strings for text fields, keep None for date fields
        for key, value in vehicle_data.items():
            if value is None and key not in ['created_at', 'updated_at'] and not key.endswith('_date'):
                vehicle_data[key] = ''
        
        response = supabase.table('vehicle_annual_records').select('id').eq('vehicle_id', vehicle_id).execute()
        
        if response.data and len(response.data) > 0:
            # Update existing record
            record_id = response.data[0]['id']
            vehicle_data['updated_at'] = datetime.now().isoformat()
            result = supabase.table('vehicle_annual_records').update(vehicle_data).eq('id', record_id).execute()
        else:
            # Insert new record
            vehicle_data['created_at'] = datetime.now().isoformat()
            vehicle_data['updated_at'] = datetime.now().isoformat()
            result = supabase.table('vehicle_annual_records').insert(vehicle_data).execute()
        
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error saving vehicle annual record: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_vehicle_annual_record(vehicle_id):
    """Get vehicle annual record by vehicle ID"""
    try:
        response = supabase.table('vehicle_annual_records').select('*').eq('vehicle_id', vehicle_id).execute()
        return response.data[0] if response.data and len(response.data) > 0 else None
    except Exception as e:
        print(f"Error getting vehicle annual record: {e}")
        return None

def save_vehicle_permanent_record(vehicle_data):
    """Save or update vehicle permanent record"""
    try:
        # Check if record exists for this vehicle
        vehicle_id = vehicle_data.get('vehicle_id')
        
        # Convert None values to empty strings for text fields
        for key, value in vehicle_data.items():
            if value is None and key not in ['created_at', 'updated_at']:
                vehicle_data[key] = ''
        
        response = supabase.table('vehicle_permanent_records').select('id').eq('vehicle_id', vehicle_id).execute()
        
        if response.data and len(response.data) > 0:
            # Update existing record
            record_id = response.data[0]['id']
            vehicle_data['updated_at'] = datetime.now().isoformat()
            result = supabase.table('vehicle_permanent_records').update(vehicle_data).eq('id', record_id).execute()
        else:
            # Insert new record
            vehicle_data['created_at'] = datetime.now().isoformat()
            vehicle_data['updated_at'] = datetime.now().isoformat()
            result = supabase.table('vehicle_permanent_records').insert(vehicle_data).execute()
        
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error saving vehicle permanent record: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_vehicle_permanent_record(vehicle_id):
    """Get vehicle permanent record by vehicle ID"""
    try:
        response = supabase.table('vehicle_permanent_records').select('*').eq('vehicle_id', vehicle_id).execute()
        return response.data[0] if response.data and len(response.data) > 0 else None
    except Exception as e:
        print(f"Error getting vehicle permanent record: {e}")
        return None

def save_trip_opening_checklist(checklist_entries):
    """Save multiple trip opening checklist entries"""
    try:
        saved_count = 0
        for entry in checklist_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['check_date', 'check_time', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('trip_opening_checklist').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving trip opening checklist: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_utilization_record(utilization_entries):
    """Save multiple utilization record entries"""
    try:
        saved_count = 0
        for entry in utilization_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['opening_time', 'closing_time', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('utilization_record').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving utilization record: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_fuel_consumption(fuel_entries):
    """Save multiple fuel consumption entries"""
    try:
        saved_count = 0
        for entry in fuel_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['date', 'bill_date', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('fuel_consumption').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving fuel consumption: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_daily_technical_remarks(remarks_entries):
    """Save multiple daily technical remarks entries"""
    try:
        saved_count = 0
        for entry in remarks_entries:
            # Only save rows that have at least one meaningful field filled in
            meaningful = any(
                str(entry.get(f, '') or '').strip()
                for f in ['drivers_voice', 'technical_observation', 'day_end_status',
                          'materials_purchased', 'supplier_bill', 'amount']
            )
            if not meaningful:
                continue

            # Build a clean payload matching the DB schema exactly
            # Schema: vehicle_id TEXT, registration_no TEXT, date DATE,
            #         kilometer TEXT, drivers_voice TEXT, technical_observation TEXT,
            #         day_end_status TEXT, materials_purchased TEXT,
            #         supplier_bill TEXT, amount NUMERIC(12,2)
            clean = {
                'vehicle_id':         str(entry.get('vehicle_id') or ''),
                'registration_no':    str(entry.get('registration_no') or ''),
                'date':               entry.get('date') or None,
                'kilometer':          str(entry.get('kilometer') or ''),
                'drivers_voice':      str(entry.get('drivers_voice') or ''),
                'technical_observation': str(entry.get('technical_observation') or ''),
                'day_end_status':     str(entry.get('day_end_status') or ''),
                'materials_purchased': str(entry.get('materials_purchased') or ''),
                'supplier_bill':      str(entry.get('supplier_bill') or ''),
            }
            # amount: numeric or NULL
            raw_amount = str(entry.get('amount') or '').strip()
            try:
                clean['amount'] = float(raw_amount) if raw_amount else None
            except ValueError:
                clean['amount'] = None
            # Let DB default handle created_at / updated_at – do NOT send them

            # Insert using the clean payload
            try:
                print('Inserting daily_technical_remarks clean payload:', clean)
                result = supabase.table('daily_technical_remarks').insert(clean).execute()
                print('Supabase insert data:', getattr(result, 'data', None))
                print('Supabase insert error:', getattr(result, 'error', None))
            except Exception as exc:
                print('Supabase insert raised exception:', exc)
                import traceback
                traceback.print_exc()
                continue

            if getattr(result, 'data', None):
                saved_count += 1
            else:
                print('Insert returned no data for payload:', clean)
        
        return saved_count
    except Exception as e:
        print(f"Error saving daily technical remarks: {e}")
        import traceback
        traceback.print_exc()
        return 0


def get_all_daily_technical_remarks(limit=1000):
    """Return recent daily technical remarks records (most recent first)."""
    try:
        cols = 'id, vehicle_id, registration_no, date, kilometer, drivers_voice, technical_observation, day_end_status, materials_purchased, supplier_bill, amount, created_at'
        response = supabase.table('daily_technical_remarks').select(cols).order('created_at', desc=True).range(0, limit - 1).execute()
        print(f'get_all_daily_technical_remarks: fetched {len(response.data or [])} records')
        return response.data if response.data else []
    except Exception as e:
        print(f'Error getting daily technical remarks: {e}')
        import traceback
        traceback.print_exc()
        return []


def get_daily_technical_remark_by_id(rem_id):
    """Return a single daily technical remark by id or None."""
    try:
        cols = 'id, vehicle_id, registration_no, date, kilometer, drivers_voice, technical_observation, day_end_status, materials_purchased, supplier_bill, amount, created_at'
        response = supabase.table('daily_technical_remarks').select(cols).eq('id', rem_id).execute()
        if getattr(response, 'data', None):
            return response.data[0]
        return None
    except Exception as e:
        print(f'Error fetching daily technical remark {rem_id}: {e}')
        import traceback
        traceback.print_exc()
        return None


def update_daily_technical_remark(rem_id, update_data):
    """Update a daily_technical_remarks row by id. Returns updated row or None."""
    try:
        allowed = {'date', 'vehicle_id', 'registration_no', 'kilometer', 'drivers_voice', 'technical_observation', 'day_end_status', 'materials_purchased', 'supplier_bill', 'amount'}
        clean = {}
        for k, v in update_data.items():
            if k in allowed:
                # keep values as-is except normalize empty strings
                if v is None:
                    clean[k] = None
                else:
                    clean[k] = v

        # Normalize amount
        if 'amount' in clean:
            raw_amount = str(clean.get('amount') or '').strip()
            try:
                clean['amount'] = float(raw_amount) if raw_amount != '' else None
            except ValueError:
                clean['amount'] = None

        # Set updated_at if DB uses it (safe to include)
        try:
            from datetime import datetime
            clean['updated_at'] = datetime.now().isoformat()
        except Exception:
            pass

        res = supabase.table('daily_technical_remarks').update(clean).eq('id', rem_id).execute()
        return res.data[0] if getattr(res, 'data', None) else None
    except Exception as e:
        print(f'Error updating daily technical remark {rem_id}: {e}')
        import traceback
        traceback.print_exc()
        return None

def get_daily_technical_remarks_page(page=1, per_page=10):
    """Return a page of daily technical remarks and a has_more flag.

    Uses Supabase range query to fetch (per_page+1) records so we can
    determine whether there is a next page without an extra count query.
    """
    try:
        if page < 1:
            page = 1
        start = (page - 1) * per_page
        end = start + per_page  # fetch one extra to detect more
        cols = 'id, vehicle_id, registration_no, date, kilometer, drivers_voice, technical_observation, day_end_status, materials_purchased, supplier_bill, amount, created_at'
        response = supabase.table('daily_technical_remarks').select(cols).order('created_at', desc=True).range(start, end).execute()
        data = response.data or []
        has_more = len(data) > per_page
        if has_more:
            data = data[:per_page]
        return {
            'records': data,
            'page': page,
            'per_page': per_page,
            'has_more': has_more
        }
    except Exception as e:
        print(f'Error paginating daily technical remarks: {e}')
        import traceback
        traceback.print_exc()
        return {'records': [], 'page': page, 'per_page': per_page, 'has_more': False}


def get_daily_technical_remarks_by_vehicle_date(vehicle_id, date_str):
    """Return all daily technical remarks rows matching vehicle_id and date.

    date_str should be 'YYYY-MM-DD'.  The query filters on the `date` column;
    if no rows match we also try matching on the date portion of `created_at`
    so older records saved without an explicit date are still found.
    """
    try:
        cols = 'id, vehicle_id, registration_no, date, kilometer, drivers_voice, technical_observation, day_end_status, materials_purchased, supplier_bill, amount, created_at'
        vehicle_id_str = str(vehicle_id)
        # Primary: match on the date column
        res = supabase.table('daily_technical_remarks').select(cols) \
            .eq('vehicle_id', vehicle_id_str) \
            .eq('date', date_str) \
            .order('created_at', desc=True) \
            .execute()
        data = res.data or []
        # Fallback: if not found, match created_at date portion
        if not data:
            day_start = date_str + 'T00:00:00'
            day_end   = date_str + 'T23:59:59'
            res2 = supabase.table('daily_technical_remarks').select(cols) \
                .eq('vehicle_id', vehicle_id_str) \
                .gte('created_at', day_start) \
                .lte('created_at', day_end) \
                .order('created_at', desc=True) \
                .execute()
            data = res2.data or []
        return data
    except Exception as e:
        print(f'Error fetching daily technical remarks by vehicle/date: {e}')
        import traceback
        traceback.print_exc()
        return []


def save_maintenance_entry(entry_data):
    """Save a single maintenance job card entry to `maintenance_entry` table."""
    try:
        # Defensive: whitelist only known columns so unexpected keys don't cause DB errors
        allowed = {
            'entry_no', 'date_time', 'vehicle_id', 'current_km', 'registration_no', 'driver_incharge',
            'drivers_voice', 'technician_alloted', 'technician_observation', 'possible_ways',
            'parts_required', 'processed_by', 'approved', 'created_by', 'created_at', 'updated_at',
            'status', 'estimated_date'
        }

        clean = {}
        for k, v in entry_data.items():
            if k in allowed:
                # For text fields convert None -> empty string, but preserve None for
                # numeric/nullable columns (like vehicle_id and current_km) and
                # for timestamp/date fields so DB receives proper NULL values.
                if v is None and k not in ['date_time', 'created_at', 'updated_at', 'estimated_date', 'vehicle_id', 'current_km']:
                    clean[k] = ''
                else:
                    clean[k] = v

        # Ensure timestamps
        now_iso = datetime.now().isoformat()
        clean.setdefault('created_at', now_iso)
        clean['updated_at'] = now_iso

        # Default status for a new job card
        clean.setdefault('status', 'new')

        # Log payload for debugging when running under Flask
        try:
            current_app.logger.debug('Inserting maintenance_entry: %s', clean)
        except Exception:
            pass

        result = supabase.table('maintenance_entry').insert(clean).execute()
        # Log the raw result for debugging
        try:
            current_app.logger.debug('Supabase insert result: %s', getattr(result, '__dict__', str(result)))
        except Exception:
            pass

        # If Supabase returned an error object, raise to surface it to the caller
        err = getattr(result, 'error', None)
        if err:
            # err may be a dict or object
            msg = err.get('message') if isinstance(err, dict) and err.get('message') else str(err)
            try:
                current_app.logger.error('Supabase insert error: %s', msg)
            except Exception:
                print('Supabase insert error:', msg)
            raise RuntimeError(f"Supabase insert error: {msg}")

        return result.data[0] if result.data else None
    except Exception as e:
        # Log exception to Flask logger when available, otherwise print
        try:
            current_app.logger.exception('Error saving maintenance entry')
        except Exception:
            print(f"Error saving maintenance entry: {e}")
            import traceback
            traceback.print_exc()
        return None


def update_maintenance_entry(entry_id, update_data):
    """Update a maintenance_entry row by id."""
    try:
        update_data['updated_at'] = datetime.now().isoformat()
        res = supabase.table('maintenance_entry').update(update_data).eq('id', entry_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Error updating maintenance entry {entry_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_weekly_attention(attention_entries):
    """Save multiple weekly attention entries"""
    try:
        saved_count = 0
        for entry in attention_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['week1_date', 'week2_date', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('weekly_attention').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving weekly attention: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_driver_voice(voice_entries):
    """Save multiple driver voice entries"""
    try:
        saved_count = 0
        for entry in voice_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['date', 'time', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('driver_voice').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving driver voice: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_technician_observation_works(works_entries):
    """Save multiple technician observation works entries"""
    try:
        saved_count = 0
        for entry in works_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['date', 'time', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('technician_observation_works').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving technician observation works: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_technician_observation_materials(materials_entries):
    """Save multiple technician observation materials entries"""
    try:
        saved_count = 0
        for entry in materials_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['date', 'time', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('technician_observation_materials').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving technician observation materials: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_process_of_works(process_entries):
    """Save multiple process of works entries"""
    try:
        saved_count = 0
        for entry in process_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['date', 'time', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('process_of_works').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving process of works: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_monthly_maintenance(maintenance_data):
    """Save monthly maintenance record"""
    try:
        # Convert None to empty string for TEXT fields
        for key, value in maintenance_data.items():
            if value is None and key not in ['created_at', 'updated_at'] and not key.startswith('processed_date_'):
                maintenance_data[key] = ''
        
        # Add timestamps
        maintenance_data['created_at'] = datetime.now().isoformat()
        maintenance_data['updated_at'] = datetime.now().isoformat()
        
        # Insert the record
        result = supabase.table('monthly_maintenance').insert(maintenance_data).execute()
        
        if result.data:
            return 1
        return 0
    except Exception as e:
        print(f"Error saving monthly maintenance: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_halfyearly_maintenance(maintenance_data):
    """Save half-yearly maintenance record"""
    try:
        # Convert None to empty string for TEXT fields
        for key, value in maintenance_data.items():
            if value is None and key not in ['created_at', 'updated_at'] and not key.startswith('processed_date_'):
                maintenance_data[key] = ''
        
        # Add timestamps
        maintenance_data['created_at'] = datetime.now().isoformat()
        maintenance_data['updated_at'] = datetime.now().isoformat()
        
        # Insert the record
        result = supabase.table('halfyearly_maintenance').insert(maintenance_data).execute()
        
        if result.data:
            return 1
        return 0
    except Exception as e:
        print(f"Error saving half-yearly maintenance: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_annual_maintenance(maintenance_data):
    """Save annual maintenance record"""
    try:
        # Convert None to empty string for TEXT fields
        for key, value in maintenance_data.items():
            if value is None and key not in ['created_at', 'updated_at'] and not key.startswith('processed_date_'):
                maintenance_data[key] = ''
        
        # Add timestamps
        maintenance_data['created_at'] = datetime.now().isoformat()
        maintenance_data['updated_at'] = datetime.now().isoformat()
        
        # Insert the record
        result = supabase.table('annual_maintenance').insert(maintenance_data).execute()
        
        if result.data:
            return 1
        return 0
    except Exception as e:
        print(f"Error saving annual maintenance: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_annual_summary_complaints(complaint_entries):
    """Save multiple annual summary complaint entries"""
    try:
        saved_count = 0
        for entry in complaint_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['date', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('annual_summary_complaints').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving annual summary complaints: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_annual_summary_recommendations(recommendation_entries):
    """Save multiple annual summary recommendation entries"""
    try:
        saved_count = 0
        for entry in recommendation_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['approx_date', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('annual_summary_recommendations').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving annual summary recommendations: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_incidents_reports_incidents(incident_entries):
    """Save multiple incident entries"""
    try:
        saved_count = 0
        for entry in incident_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['date', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('incidents_reports_incidents').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving incidents: {e}")
        import traceback
        traceback.print_exc()
        return 0

def save_incidents_reports_claims(claim_entries):
    """Save multiple claim entries"""
    try:
        saved_count = 0
        for entry in claim_entries:
            # Convert None to empty string for TEXT fields
            for key, value in entry.items():
                if value is None and key not in ['approx_date', 'created_at', 'updated_at']:
                    entry[key] = ''
            
            # Add timestamps
            entry['created_at'] = datetime.now().isoformat()
            entry['updated_at'] = datetime.now().isoformat()
            
            # Insert the entry
            result = supabase.table('incidents_reports_claims').insert(entry).execute()
            if result.data:
                saved_count += 1
        
        return saved_count
    except Exception as e:
        print(f"Error saving claims: {e}")
        import traceback
        traceback.print_exc()
        return 0


# ─────────────────────────────────────────────
# Accidents / Incidents helpers
# ─────────────────────────────────────────────

def get_next_accident_entry_no():
    """Return the next entry number in the format PMC/LOGI/INCIDENT/001.

    Falls back to parsing older formats (e.g. AI-0001) if present.
    """
    prefix = 'PMC/LOGI/INCIDENT/'
    try:
        result = supabase.table('accidents_incidents').select('entry_no').execute()
        rows = result.data or []
        max_n = 0
        for row in rows:
            en = (row.get('entry_no') or '').strip()
            if not en:
                continue
            # New format: PMC/LOGI/INCIDENT/###
            if en.startswith(prefix):
                try:
                    num = int(en.split('/')[-1])
                    max_n = max(max_n, num)
                except Exception:
                    continue
            # Legacy format support: AI-0001 or AI-001
            elif en.startswith('AI-'):
                try:
                    num = int(en.split('-')[-1])
                    max_n = max(max_n, num)
                except Exception:
                    continue
        next_n = max_n + 1
        return f"{prefix}{next_n:03d}"
    except Exception as e:
        print(f"Error getting next accident entry no: {e}")
        return f"{prefix}001"


def save_accident_incident(data, settlement_persons=None):
    """Save one accident/incident record and its settlement persons."""
    try:
        now = datetime.now().isoformat()
        data.setdefault('created_at', now)
        data['updated_at'] = now
        result = supabase.table('accidents_incidents').insert(data).execute()
        if not result.data:
            return None
        incident_id = result.data[0]['id']
        # Save settlement persons
        if settlement_persons:
            for name in settlement_persons:
                name = name.strip()
                if name:
                    supabase.table('accidents_incidents_settlement_persons').insert({
                        'incident_id': incident_id,
                        'person_name': name
                    }).execute()
        return result.data[0]
    except Exception as e:
        print(f"Error saving accident/incident: {e}")
        import traceback; traceback.print_exc()
        return None


def get_all_accidents_incidents():
    """Return all accident/incident records, newest first."""
    try:
        result = supabase.table('accidents_incidents').select('*').order('created_at', desc=True).execute()
        return result.data or []
    except Exception as e:
        print(f"Error getting accidents: {e}")
        return []


def get_accident_incident_by_id(incident_id):
    """Return a single accident/incident with its settlement persons."""
    try:
        result = supabase.table('accidents_incidents').select('*').eq('id', incident_id).execute()
        if not result.data:
            return None
        record = result.data[0]
        sp = supabase.table('accidents_incidents_settlement_persons').select('*').eq('incident_id', incident_id).execute()
        record['settlement_persons'] = [r['person_name'] for r in (sp.data or [])]
        return record
    except Exception as e:
        print(f"Error getting accident by id: {e}")
        return None


def save_feedback(feedback_data):
    """Save feedback submission"""
    try:
        # Convert None to empty string for TEXT fields
        for key, value in feedback_data.items():
            if value is None and key not in ['rating', 'created_at', 'updated_at']:
                feedback_data[key] = ''
        
        # Add timestamps
        feedback_data['created_at'] = datetime.now().isoformat()
        feedback_data['updated_at'] = datetime.now().isoformat()
        
        # Insert the feedback
        result = supabase.table('feedback').insert(feedback_data).execute()
        
        return 1 if result.data else 0
    except Exception as e:
        print(f"Error saving feedback: {e}")
        import traceback
        traceback.print_exc()
        return 0

def get_next_purchase_entry_no():
    """Get the next purchase entry number"""
    try:
        # Get the count of existing purchases
        response = supabase.table('purchases').select('id', count='exact').execute()
        count = response.count if response.count else 0
        # Next entry number is count + 1, formatted as 001, 002, etc.
        next_no = count + 1
        return f"{next_no:03d}"
    except Exception as e:
        print(f"Error getting next purchase entry no: {e}")
        return "001"

def save_purchase(purchase_data):
    """Save purchase record"""
    try:
        # Remove user_id as it's not needed for the purchases table
        if 'user_id' in purchase_data:
            purchase_data.pop('user_id')
        
        # Convert empty strings to None for numeric fields
        numeric_fields = ['quantity', 'rate', 'discount_percent', 'discount_amount', 
                          'taxable_amount', 'sgst_percent', 'sgst_amount', 
                          'cgst_percent', 'cgst_amount', 'igst_percent', 'igst_amount',
                          'total_payment', 'dn', 'less_tds', 'net_payable']
        
        for field in numeric_fields:
            if field in purchase_data and purchase_data[field] == '':
                purchase_data[field] = None
            elif field in purchase_data and purchase_data[field]:
                purchase_data[field] = float(purchase_data[field])
        
        # Convert empty strings to None for date fields
        date_fields = ['date', 'invoice_date']
        for field in date_fields:
            if field in purchase_data and purchase_data[field] == '':
                purchase_data[field] = None
        
        # Convert empty strings to None for text fields
        text_fields = ['time', 'invoice_no', 'vendor', 'type_of_purchase', 'part_number', 
                       'part_name', 'batch_number', 'entry_no']
        for field in text_fields:
            if field in purchase_data and purchase_data[field] == '':
                purchase_data[field] = None
        
        # Add timestamps (set per-attempt to keep unique entry_no generation accurate)
        import copy

        max_attempts = 6
        for attempt in range(max_attempts):
            pdata = copy.deepcopy(purchase_data)
            pdata['created_at'] = datetime.now().isoformat()
            pdata['updated_at'] = datetime.now().isoformat()

            # If entry_no not provided, ask DB function for next entry (RPC). If RPC fails, fallback to local function
            if not pdata.get('entry_no'):
                try:
                    rpc_res = supabase.rpc('get_next_purchase_entry_no').execute()
                    if rpc_res and rpc_res.data:
                        # RPC may return scalar or list depending on client; handle both
                        if isinstance(rpc_res.data, list) and len(rpc_res.data) > 0:
                            pdata['entry_no'] = str(rpc_res.data[0])
                        else:
                            pdata['entry_no'] = str(rpc_res.data)
                    else:
                        pdata['entry_no'] = get_next_purchase_entry_no()
                except Exception:
                    pdata['entry_no'] = get_next_purchase_entry_no()

            try:
                print(f"[save_purchase] attempt={attempt+1} trying entry_no={pdata.get('entry_no')}")
                result = supabase.table('purchases').insert(pdata).execute()
                if result.data:
                    print(f"[save_purchase] success entry_no={pdata.get('entry_no')}")
                    return 1
                # If insert returned no data but no exception, treat as failure and retry
                print(f"[save_purchase] insert returned no data for entry_no={pdata.get('entry_no')}")
            except Exception as e:
                msg = str(e).lower()
                print(f"[save_purchase] insert error for entry_no={pdata.get('entry_no')}: {msg}")
                # if duplicate key error on entry_no, retry by asking DB for a new entry_no
                if 'duplicate key' in msg or '23505' in msg:
                    continue
                # other errors: raise
                raise

        # If we exhausted retries, attempt a final fallback with a timestamp-based unique entry_no
        try:
            pdata = copy.deepcopy(purchase_data)
            pdata['created_at'] = datetime.now().isoformat()
            pdata['updated_at'] = datetime.now().isoformat()
            pdata['entry_no'] = 'TMP' + datetime.now().strftime('%Y%m%d%H%M%S%f')
            print(f"[save_purchase] fallback attempt with entry_no={pdata['entry_no']}")
            result = supabase.table('purchases').insert(pdata).execute()
            if result.data:
                print(f"[save_purchase] fallback success entry_no={pdata['entry_no']}")
                return 1
        except Exception as e:
            print('Fallback insert failed:', e)

        # If fallback also failed, raise
        raise Exception('Failed to save purchase after multiple attempts due to duplicate entry_no')
    except Exception as e:
        error_msg = f"Error saving purchase: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        raise Exception(error_msg)


def _get_next_dc_number():
    """Return next DC number as zero-padded 3-digit string based on last entry."""
    try:
        try:
            res = supabase.table('dc_entries').select('dc_no').order('created_at', desc=True).limit(1).execute()
            if res.data and len(res.data) > 0:
                last = res.data[0].get('dc_no') or ''
                import re
                m = re.search(r"(\d+)$", str(last))
                if m:
                    next_no = int(m.group(1)) + 1
                    return f"{next_no:03d}"
        except Exception:
            pass

        # Fallback to count-based
        response = supabase.table('dc_entries').select('id', count='exact').execute()
        count = response.count if response.count else 0
        next_no = count + 1
        return f"{next_no:03d}"
    except Exception as e:
        print(f"Error getting next dc number: {e}")
        return "001"


def save_dc_entry(header, rows, created_by=None):
    """Save a DC entry and its line items to Supabase.

    header: dict of header fields
    rows: list of dicts for each row
    created_by: optional user id
    Returns inserted dc_entries record or None on failure
    """
    try:
        global _last_dc_save_error
        _last_dc_save_error = None

        def _clean_item_value(value):
            return None if value is None or str(value).strip() == '' else value

        def _normalize_sl_no(value, fallback):
            cleaned = _clean_item_value(value)
            if cleaned is None:
                return fallback
            try:
                return int(cleaned)
            except Exception:
                return fallback

        def _normalize_return_date(value):
            cleaned = _clean_item_value(value)
            if cleaned is None:
                return None
            if isinstance(cleaned, datetime):
                return cleaned.date().isoformat()

            s = str(cleaned).strip()
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    return datetime.strptime(s, fmt).date().isoformat()
                except Exception:
                    continue
            # If value is not parseable as date, store NULL instead of failing insert.
            return None

        def _normalize_header_date(value):
            # Accept empty -> NULL, datetime -> YYYY-MM-DD, or try common formats
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.date().isoformat()
            s = str(value).strip()
            if s == '':
                return None
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    return datetime.strptime(s, fmt).date().isoformat()
                except Exception:
                    continue
            # If parsing fails, return None to avoid DB errors
            return None

        def _build_dc_items_payload(entry_id, dc_rows):
            items_payload = []
            for idx, r in enumerate(dc_rows or []):
                part_no = _clean_item_value(r.get('part_no'))
                ref_no = _clean_item_value(r.get('ref_no'))
                particulars = _clean_item_value(r.get('particulars'))
                qty = _clean_item_value(r.get('qty'))
                reason = _clean_item_value(r.get('reason'))
                return_date = _clean_item_value(r.get('return_date'))
                return_status = _clean_item_value(r.get('return_status'))
                remarks = _clean_item_value(r.get('remarks'))

                # Skip placeholder rows that are fully empty.
                if not any([part_no, ref_no, particulars, qty, reason, return_date, return_status, remarks]):
                    continue

                item = {
                    'dc_entry_id': entry_id,
                    'sl_no': _normalize_sl_no(r.get('sl_no'), idx + 1),
                    'part_no': part_no,
                    'ref_no': ref_no,
                    'particulars': particulars,
                    'qty': qty,
                    'reason': reason,
                    'return_date': _normalize_return_date(return_date),
                    'return_status': return_status,
                    'remarks': remarks
                }
                items_payload.append(item)
            return items_payload

        import copy
        max_attempts = 6
        for attempt in range(max_attempts):
            pdata = copy.deepcopy(header)
            pdata['created_at'] = datetime.now().isoformat()
            pdata['updated_at'] = datetime.now().isoformat()
            if created_by:
                try:
                    pdata['created_by'] = int(created_by) if str(created_by).isdigit() else created_by
                except Exception:
                    pdata['created_by'] = created_by
            # Normalize optional header date to avoid invalid date string inserts
            try:
                pdata['date'] = _normalize_header_date(pdata.get('date'))
            except Exception:
                pdata['date'] = None

            # Always assign a fresh incremented dc_no for each submit.
            try:
                rpc_res = supabase.rpc('get_next_dc_entry_no').execute()
                if rpc_res and rpc_res.data:
                    if isinstance(rpc_res.data, list) and len(rpc_res.data) > 0:
                        num = str(rpc_res.data[0])
                    else:
                        num = str(rpc_res.data)
                    pdata['dc_no'] = 'PMC/LOGI/DC/' + num.zfill(3)
                else:
                    pdata['dc_no'] = 'PMC/LOGI/DC/' + _get_next_dc_number()
            except Exception:
                pdata['dc_no'] = 'PMC/LOGI/DC/' + _get_next_dc_number()

            try:
                res = supabase.table('dc_entries').insert(pdata).execute()
                if res.data:
                    entry = res.data[0]
                    entry_id = entry.get('id')

                    # Insert only meaningful line items and normalize empty values.
                    items = _build_dc_items_payload(entry_id, rows)

                    if items:
                        try:
                            supabase.table('dc_items').insert(items).execute()
                        except Exception as item_bulk_error:
                            print(f"save_dc_entry: bulk dc_items insert failed, trying row-by-row. error={item_bulk_error}")
                            inserted_any = False
                            for item in items:
                                try:
                                    supabase.table('dc_items').insert(item).execute()
                                    inserted_any = True
                                except Exception as one_item_error:
                                    print(f"save_dc_entry: skipped invalid item {item}. error={one_item_error}")
                            if not inserted_any:
                                print("save_dc_entry: dc header saved but no valid item rows inserted")

                    return entry
                else:
                    print(f"save_dc_entry: insert returned no data on attempt {attempt+1}")
            except Exception as e:
                msg = str(e).lower()
                print(f"save_dc_entry: attempt {attempt+1} insert error: {msg}")
                # Duplicate key on dc_no? retry
                if 'duplicate key' in msg or '23505' in msg:
                    continue
                # Other errors: raise
                raise

        # Final fallback: timestamp-based temporary dc_no
        try:
            pdata = copy.deepcopy(header)
            pdata['created_at'] = datetime.now().isoformat()
            pdata['updated_at'] = datetime.now().isoformat()
            pdata['dc_no'] = 'TMP' + datetime.now().strftime('%Y%m%d%H%M%S%f')
            try:
                pdata['date'] = _normalize_header_date(pdata.get('date'))
            except Exception:
                pdata['date'] = None
            res = supabase.table('dc_entries').insert(pdata).execute()
            if res.data:
                entry = res.data[0]
                entry_id = entry.get('id')
                items = _build_dc_items_payload(entry_id, rows)
                if items:
                    try:
                        supabase.table('dc_items').insert(items).execute()
                    except Exception as item_bulk_error:
                        print(f"save_dc_entry fallback: bulk dc_items insert failed, trying row-by-row. error={item_bulk_error}")
                        for item in items:
                            try:
                                supabase.table('dc_items').insert(item).execute()
                            except Exception as one_item_error:
                                print(f"save_dc_entry fallback: skipped invalid item {item}. error={one_item_error}")
                return entry
        except Exception as e:
            print('save_dc_entry fallback failed:', e)
            _last_dc_save_error = str(e)

        # All attempts failed
        raise Exception('Failed to save dc entry after multiple attempts')
    except Exception as e:
        print(f"Error saving dc entry: {e}")
        import traceback
        traceback.print_exc()
        _last_dc_save_error = str(e)
        return None


_last_dc_save_error = None


def get_last_dc_save_error():
    return _last_dc_save_error


def get_all_dc_entries(limit=200):
    """Return list of recent DC entries that have NOT been given a Returnable/Non-Returnable status."""
    try:
        res = supabase.table('dc_entries').select('*').order('created_at', desc=True).limit(limit).execute()
        all_entries = res.data or []
        if not all_entries:
            return []
        # Collect entry IDs that already have a processed item status
        proc_res = supabase.table('dc_items').select('dc_entry_id').in_('return_status', ['Returnable', 'Non-Returnable']).execute()
        processed_ids = set(str(row['dc_entry_id']) for row in (proc_res.data or []))
        return [e for e in all_entries if str(e.get('id')) not in processed_ids]
    except Exception as e:
        print(f"Error fetching dc entries: {e}")
        return []


def update_dc_item_status(entry_id, item_index, status, return_date=None, remarks=None):
    """Update a dc_items row (by dc_entry_id + sl_no/order offset) with new status, return_date and remarks."""
    try:
        query_val = entry_id
        try:
            if isinstance(entry_id, str) and entry_id.isdigit():
                query_val = int(entry_id)
        except Exception:
            pass
        # Fetch items for this entry ordered by id
        items_res = supabase.table('dc_items').select('id').eq('dc_entry_id', query_val).order('id', desc=False).execute()
        items = items_res.data or []
        if not items or item_index < 0 or item_index >= len(items):
            return False, 'Item not found'
        item_id = items[item_index]['id']
        payload = {'return_status': status}
        if return_date is not None:
            payload['return_date'] = return_date if return_date else None
        if remarks is not None:
            payload['remarks'] = remarks
        supabase.table('dc_items').update(payload).eq('id', item_id).execute()
        return True, 'Updated'
    except Exception as e:
        print(f'update_dc_item_status error: {e}')
        return False, str(e)


def get_dc_items_by_status(status_filter=None, limit=500):
    """Return all dc_items joined with their entry header, optionally filtered by return_status."""
    try:
        q = supabase.table('dc_items').select('*, dc_entries(dc_no, to_name, date)').order('id', desc=True).limit(limit)
        if status_filter:
            q = q.eq('return_status', status_filter)
        res = q.execute()
        return res.data or []
    except Exception as e:
        print(f'get_dc_items_by_status error: {e}')
        return []


def get_dc_entry(entry_id):
    """Return a dict with header and rows for a specific entry id."""
    try:
        # Accept numeric strings as integers (Supabase may store ids as integers)
        query_val = entry_id
        try:
            if isinstance(entry_id, str) and entry_id.isdigit():
                query_val = int(entry_id)
        except Exception:
            query_val = entry_id

        h = supabase.table('dc_entries').select('*').eq('id', query_val).execute()
        if not h.data or len(h.data) == 0:
            # Fallback: if direct id match failed, try matching dc_no (some callers may pass dc_no)
            try:
                fb = supabase.table('dc_entries').select('*').eq('dc_no', entry_id).execute()
                if fb.data and len(fb.data) > 0:
                    header = fb.data[0]
                else:
                    return None
            except Exception:
                return None
        else:
            header = h.data[0]
        # Build candidate key variants because some clients surface bigint ids as
        # strings while others use integers.
        candidates = []

        def _push_candidate(v):
            if v is None:
                return
            if v not in candidates:
                candidates.append(v)

        try:
            entry_pk = header.get('id') if header and header.get('id') is not None else query_val
        except Exception:
            entry_pk = query_val

        _push_candidate(entry_pk)
        _push_candidate(query_val)

        for v in [entry_pk, query_val, entry_id]:
            try:
                if isinstance(v, str):
                    s = v.strip()
                    _push_candidate(s)
                    if s.isdigit():
                        _push_candidate(int(s))
                elif isinstance(v, int):
                    _push_candidate(str(v))
            except Exception:
                continue

        rows = []
        for key in candidates:
            try:
                items = supabase.table('dc_items').select('*').eq('dc_entry_id', key).order('id', desc=False).execute()
                rows = items.data or []
                if rows:
                    break
            except Exception:
                continue

        # Prefer sl_no ordering where present, then id for stable display.
        rows = sorted(
            rows,
            key=lambda r: (
                r.get('sl_no') is None,
                r.get('sl_no') if r.get('sl_no') is not None else 10**9,
                r.get('id') if r.get('id') is not None else 0,
            ),
        )
        return {'header': header, 'rows': rows}
    except Exception as e:
        print(f"Error getting dc entry {entry_id}: {e}")
        return None

# =====================================================
# FUEL MANAGEMENT FUNCTIONS
# =====================================================

def get_next_fuel_entry_no():
    """Get the next fuel entry number"""
    try:
        # Prefer reading the most recent entry and incrementing its trailing number.
        # This avoids an expensive exact count on large tables in some backends.
        try:
            res = supabase.table('fuel').select('entry_no').order('created_at', desc=True).limit(1).execute()
            if res.data and len(res.data) > 0:
                last_en = res.data[0].get('entry_no') or ''
                import re
                m = re.search(r"(\d+)$", str(last_en))
                if m:
                    next_no = int(m.group(1)) + 1
                    return f"{next_no:03d}"
        except Exception:
            # fallthrough to count-based fallback
            pass

        # Fallback to exact count if we couldn't parse last entry
        response = supabase.table('fuel').select('id', count='exact').execute()
        count = response.count if response.count else 0
        next_no = count + 1
        return f"{next_no:03d}"
    except Exception as e:
        print(f"Error getting next fuel entry no: {e}")
        return "001"

def save_fuel(fuel_data):
    """Save fuel record"""
    try:
        # Convert empty strings to None for numeric fields
        numeric_fields = ['quantity', 'rate', 'amount', 'km_reading', 'mileage']  # 'mileage' stores distance traveled
        
        for field in numeric_fields:
            if field in fuel_data and fuel_data[field] == '':
                fuel_data[field] = None
            elif field in fuel_data and fuel_data[field]:
                fuel_data[field] = float(fuel_data[field])
        
        # Convert empty strings to None for date fields
        date_fields = ['date']
        for field in date_fields:
            if field in fuel_data and fuel_data[field] == '':
                fuel_data[field] = None
        
        # Convert empty strings to None for text fields
        text_fields = ['time', 'entry_no', 'bill_no', 'type_of_purchase', 'part_no', 
                       'part_name', 'rate_id', 'vehicle_reg_no', 'driver']
        for field in text_fields:
            if field in fuel_data and fuel_data[field] == '':
                fuel_data[field] = None
        
        # Add timestamps
        fuel_data['created_at'] = datetime.now().isoformat()
        fuel_data['updated_at'] = datetime.now().isoformat()
        
        # Insert the fuel record
        result = supabase.table('fuel').insert(fuel_data).execute()
        
        return 1 if result.data else 0
    except Exception as e:
        print(f"Error saving fuel: {e}")
        import traceback
        traceback.print_exc()
        return 0

# =====================================================
# STOCK STORE MANAGEMENT FUNCTIONS
# =====================================================

def get_next_stock_entry_no():
    """Get the next stock entry number"""
    try:
        # Get the count of existing stock records
        response = supabase.table('stock').select('id', count='exact').execute()
        count = response.count if response.count else 0
        # Next entry number is count + 1, formatted as 001, 002, etc.
        next_no = count + 1
        return f"{next_no:03d}"
    except Exception as e:
        print(f"Error getting next stock entry no: {e}")
        return "001"

def save_stock(stock_items):
    """Save multiple stock records"""
    try:
        inserted_count = 0
        
        for item in stock_items:
            # Convert empty strings to None for numeric fields
            if 'kilometer' in item and item['kilometer'] == '':
                item['kilometer'] = None
            elif 'kilometer' in item and item['kilometer']:
                item['kilometer'] = float(item['kilometer'])
            
            # Convert empty strings to None for date fields
            if 'date' in item and item['date'] == '':
                item['date'] = None
            
            # Convert empty strings to None for text fields
            text_fields = ['time', 'part_no', 'part_name', 'vehicle_no', 'vehicle_id',
                          'issuing_person', 'driver_responsible', 'mechanic_responsible', 'comments']
            for field in text_fields:
                if field in item and item['field'] == '':
                    item[field] = None
            
            # Add timestamps
            item['created_at'] = datetime.now().isoformat()
            item['updated_at'] = datetime.now().isoformat()
            
            # Insert the stock record
            result = supabase.table('stock').insert(item).execute()
            
            if result.data:
                inserted_count += 1
        
        return inserted_count
    except Exception as e:
        print(f"Error saving stock: {e}")
        import traceback
        traceback.print_exc()
        return 0

# =====================================================
# STATUTORY MANAGEMENT FUNCTIONS
# =====================================================

def get_next_statutory_entry_no():
    """Get the next statutory entry number"""
    try:
        # Get the count of existing statutory records
        response = supabase.table('statutory').select('id', count='exact').execute()
        count = response.count if response.count else 0
        # Next entry number is count + 1, formatted as 001, 002, etc.
        next_no = count + 1
        return f"{next_no:03d}"
    except Exception as e:
        print(f"Error getting next statutory entry no: {e}")
        return "001"

def save_statutory(statutory_data):
    """Save statutory record"""
    try:
        # Convert empty strings to None for numeric fields
        numeric_fields = ['rate', 'taxable_amount', 'sgst_percent', 'sgst_amount', 
                         'cgst_percent', 'cgst_amount', 'igst_percent', 'igst_amount', 'total_amount']
        
        for field in numeric_fields:
            if field in statutory_data and statutory_data[field] == '':
                statutory_data[field] = None
            elif field in statutory_data and statutory_data[field]:
                statutory_data[field] = float(statutory_data[field])
        
        # Convert empty strings to None for date fields
        date_fields = ['date', 'invoice_date', 'validity_date']
        for field in date_fields:
            if field in statutory_data and statutory_data[field] == '':
                statutory_data[field] = None
        
        # Convert empty strings to None for text fields
        text_fields = ['time', 'entry_no', 'invoice_no', 'statutory_body_id', 
                       'vehicle_id', 'registration_no',
                       'type_of_transaction', 'entered_by', 'approved_by',
                       'approver_name', 'rejection_reason']
        for field in text_fields:
            if field in statutory_data and statutory_data[field] == '':
                statutory_data[field] = None
        
        # Add timestamps
        statutory_data['created_at'] = datetime.now().isoformat()
        statutory_data['updated_at'] = datetime.now().isoformat()
        
        # Insert the statutory record
        result = supabase.table('statutory').insert(statutory_data).execute()
        
        return 1 if result.data else 0
    except Exception as e:
        print(f"Error saving statutory: {e}")
        import traceback
        traceback.print_exc()
        return 0

# =====================================================
# ADMIN MANAGEMENT FUNCTIONS
# =====================================================

def get_users_count():
    """Get total count of users"""
    try:
        response = supabase.table('users').select('id', count='exact').execute()
        return response.count if response.count else 0
    except Exception as e:
        print(f"Error getting users count: {e}")
        return 0

def get_vehicles_count():
    """Get total count of vehicles"""
    try:
        response = supabase.table('vehicles').select('id', count='exact').execute()
        return response.count if response.count else 0
    except Exception as e:
        print(f"Error getting vehicles count: {e}")
        return 0

def get_all_vehicles():
    """Get all vehicles from the vehicles table"""
    try:
        response = supabase.table('vehicles').select('*').order('created_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting all vehicles: {e}")
        return []

def get_user_by_id(user_id):
    """Get a single user by ID"""
    try:
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        return response.data[0] if response.data and len(response.data) > 0 else None
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

def get_vehicle_by_id(vehicle_id):
    """Get a single vehicle by ID"""
    try:
        response = supabase.table('vehicles').select('*').eq('id', vehicle_id).execute()
        return response.data[0] if response.data and len(response.data) > 0 else None
    except Exception as e:
        print(f"Error getting vehicle by ID: {e}")
        return None


def get_vehicle_by_vehicle_id(vehicle_id_value):
    """Get a single vehicle by its `vehicle_id` field (not the numeric PK)."""
    try:
        response = supabase.table('vehicles').select('*').eq('vehicle_id', vehicle_id_value).execute()
        return response.data[0] if response.data and len(response.data) > 0 else None
    except Exception as e:
        print(f"Error getting vehicle by vehicle_id: {e}")
        return None

def admin_create_user(user_data):
    """Create a new user (admin function)"""
    try:
        user_data['created_at'] = datetime.now().isoformat()
        user_data['updated_at'] = datetime.now().isoformat()
        response = supabase.table('users').insert(user_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def admin_update_user(user_id, user_data):
    """Update an existing user (admin function)"""
    try:
        user_data['updated_at'] = datetime.now().isoformat()
        response = supabase.table('users').update(user_data).eq('id', user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating user: {e}")
        return None

def admin_delete_user(user_id):
    """Delete a user (admin function)"""
    try:
        response = supabase.table('users').delete().eq('id', user_id).execute()
        return True if response.data else False
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False

def admin_toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        # Get current status
        user = get_user_by_id(user_id)
        if user:
            new_status = not user['is_active']
            response = supabase.table('users').update({'is_active': new_status, 'updated_at': datetime.now().isoformat()}).eq('id', user_id).execute()
            return response.data[0] if response.data else None
        return None
    except Exception as e:
        print(f"Error toggling user status: {e}")
        return None

def admin_add_vehicle(vehicle_data):
    """Add a new vehicle (admin function)"""
    try:
        vehicle_data['created_at'] = datetime.now().isoformat()
        vehicle_data['updated_at'] = datetime.now().isoformat()
        response = supabase.table('vehicles').insert(vehicle_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error adding vehicle: {e}")
        return None

def admin_update_vehicle(vehicle_id, vehicle_data):
    """Update an existing vehicle (admin function)"""
    try:
        vehicle_data['updated_at'] = datetime.now().isoformat()
        response = supabase.table('vehicles').update(vehicle_data).eq('id', vehicle_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating vehicle: {e}")
        return None

def admin_delete_vehicle(vehicle_id):
    """Delete a vehicle (admin function)"""
    try:
        response = supabase.table('vehicles').delete().eq('id', vehicle_id).execute()
        return True if response.data else False
    except Exception as e:
        print(f"Error deleting vehicle: {e}")
        return False

def get_all_fuel_records():
    """Get all fuel records with vehicle and part information"""
    try:
        # Join fuel with vehicles to get registration_no and with parts to get vendor info
        response = supabase.table('fuel').select('''
            *,
            vehicles:vehicle_id(registration_no),
            parts:part_no(part_name, vendor_name)
        ''').order('created_at', desc=True).execute()
        
        # Process the data to flatten the joined fields
        records = []
        for record in (response.data or []):
            # Flatten vehicle data
            if record.get('vehicles'):
                record['registration_no'] = record['vehicles']['registration_no']
            else:
                record['registration_no'] = '-'
            
            # Flatten parts data
            if record.get('parts'):
                record['vendor_name'] = record['parts'].get('vendor_name', '-')
            else:
                record['vendor_name'] = '-'
            
            # Map fuel table fields to expected template fields
            record['fuel_type'] = record.get('type_of_purchase', '-')
            record['invoice_no'] = record.get('bill_no', '-')
            
            records.append(record)
        
        return records
    except Exception as e:
        print(f"Error getting fuel records: {e}")
        # Fallback to basic query if join fails
        try:
            response = supabase.table('fuel').select('*').order('created_at', desc=True).execute()
            records = []
            for record in (response.data or []):
                record['registration_no'] = '-'
                record['vendor_name'] = '-'
                record['fuel_type'] = record.get('type_of_purchase', '-')
                record['invoice_no'] = record.get('bill_no', '-')
                records.append(record)
            return records
        except:
            return []

def get_all_statutory_records():
    """Get all statutory records"""
    try:
        response = supabase.table('statutory').select('*').order('created_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting statutory records: {e}")
        return []

def get_all_trip_sheets():
    """Get all trip sheet records with vehicle and driver information"""
    try:
        # PostgREST / Supabase limits response size per request (commonly 1000 rows).
        # Fetch records in chunks to ensure we return all rows when the table is large.
        chunk_size = 1000
        start = 0
        records = []
        while True:
            response = supabase.table('trip_sheet').select('''
                *,
                vehicles:vehicle_id(registration_no),
                employees:driver_id(name)
            ''').order('created_at', desc=True).range(start, start + chunk_size - 1).execute()

            batch = response.data or []
            if not batch:
                break

            # Flatten joined fields for this batch
            for record in batch:
                if record.get('vehicles'):
                    record['vehicle_no'] = record['vehicles'].get('registration_no')
                else:
                    record['vehicle_no'] = '-'

                if record.get('employees'):
                    record['driver_name'] = record['employees'].get('name')
                else:
                    record['driver_name'] = '-'

                records.append(record)

            # If this batch is smaller than chunk_size, we've fetched all rows
            if len(batch) < chunk_size:
                break

            start += chunk_size

        return records
    except Exception as e:
        print(f"Error getting trip sheet records: {e}")
        # Fallback to a single request (best-effort)
        try:
            response = supabase.table('trip_sheet').select('*').order('created_at', desc=True).execute()
            records = []
            for record in (response.data or []):
                record['vehicle_no'] = '-'
                record['driver_name'] = '-'
                records.append(record)
            return records
        except:
            return []

def get_all_purchases():
    """Get all purchase records"""
    try:
        response = supabase.table('purchases').select('*').order('created_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting purchase records: {e}")
        return []


def get_stock_totals():
    """Compute authoritative stock totals from purchases, utilization, scrap and issue register.
    Returns a dict with numeric totals (not formatted strings).
    """
    try:
        # Fetch necessary records
        purchases = supabase.table('purchases').select('*').execute()
        utilization = supabase.table('material_utilization').select('*').execute()
        scrap = supabase.table('scrap').select('*').execute()
        issue_register = supabase.table('stock_issue_register').select('*').execute()

        def _safe_float(v):
            try:
                return float(v or 0)
            except Exception:
                try:
                    return float(str(v).replace(',',''))
                except Exception:
                    return 0.0

        utilized_by_part = {}
        if utilization.data:
            for r in utilization.data:
                raw = r.get('part_no') or r.get('part_number') or ''
                if raw is None:
                    continue
                key = str(raw).strip().lower()
                utilized_by_part[key] = utilized_by_part.get(key, 0.0) + _safe_float(r.get('quantity'))

        scrapped_by_part = {}
        if scrap.data:
            for r in scrap.data:
                raw = r.get('part_no') or r.get('part_number') or ''
                if raw is None:
                    continue
                key = str(raw).strip().lower()
                scrapped_by_part[key] = scrapped_by_part.get(key, 0.0) + _safe_float(r.get('quantity'))

        parts = {}
        total_value_all_purchases = 0.0
        total_current_qty = 0.0
        if purchases.data:
            for item in purchases.data:
                raw = item.get('part_number') or item.get('part_no') or item.get('part') or ''
                if raw is None:
                    continue
                part_no = str(raw).strip()
                key = part_no.lower()
                qty = _safe_float(item.get('quantity'))
                total_value_all_purchases += _safe_float(item.get('net_payable'))
                if key not in parts:
                    parts[key] = {'part_no': part_no, 'current_qty': 0.0}
                parts[key]['current_qty'] += qty
                total_current_qty += qty

        # Debugging: print per-purchase quantities and key fields to help trace mismatches
        try:
            print("[STOCKDEBUG] Purchases rows and quantities:")
            running = 0.0
            if purchases.data:
                for item in purchases.data:
                    pid = item.get('id')
                    pn = item.get('part_number') or item.get('part_no') or item.get('part') or ''
                    qty_raw = item.get('quantity')
                    qty_val = _safe_float(qty_raw)
                    orig_qty_raw = item.get('original_quantity')
                    orig_qty_val = _safe_float(orig_qty_raw)
                    status = item.get('status')
                    ca = item.get('created_at') or item.get('invoice_date')
                    running += qty_val
                    print(f"[STOCKDEBUG] id={pid} part={pn} qty_raw={qty_raw} qty_val={qty_val} original_qty={orig_qty_raw} status={status} created_at={ca}")
            print(f"[STOCKDEBUG] summed_purchases_qty={running} computed_total_current_qty={total_current_qty}")
        except Exception:
            pass

        total_issued_qty = 0.0
        if issue_register.data:
            for r in issue_register.data:
                total_issued_qty += _safe_float(r.get('quantity_issued') or r.get('quantity') or 0)

        total_utilized_qty = sum(utilized_by_part.values())
        total_scrapped_qty = sum(scrapped_by_part.values())

        original_received_qty = total_current_qty + total_utilized_qty + total_scrapped_qty + total_issued_qty
        closing_stock_qty = total_current_qty

        # Compute values for instock/utilized/scrapped using a simple cost-per-unit map
        cost_per_unit_map = {}
        if purchases.data:
            for item in purchases.data:
                raw = item.get('part_number') or item.get('part_no') or item.get('part') or ''
                if raw is None:
                    continue
                try:
                    part_no = str(raw).strip()
                    key = part_no.lower()
                except Exception:
                    key = str(raw)
                purchased_qty = _safe_float(item.get('quantity'))
                original_qty = _safe_float(item.get('original_quantity'))
                net_payable = _safe_float(item.get('net_payable'))
                try:
                    rate_val = float(item.get('rate')) if item.get('rate') is not None else None
                except Exception:
                    rate_val = None

                if purchased_qty > 0:
                    cost_per_unit = net_payable / purchased_qty if net_payable and purchased_qty else (rate_val or 0)
                elif original_qty > 0:
                    cost_per_unit = net_payable / original_qty if net_payable and original_qty else (rate_val or 0)
                elif rate_val and rate_val > 0:
                    cost_per_unit = rate_val
                elif net_payable > 0:
                    cost_per_unit = net_payable
                else:
                    cost_per_unit = 0

                if key in cost_per_unit_map:
                    cost_per_unit_map[key] = (cost_per_unit_map[key] + cost_per_unit) / 2
                else:
                    cost_per_unit_map[key] = cost_per_unit

        utilized_value = 0.0
        for k, qty in utilized_by_part.items():
            utilized_value += qty * cost_per_unit_map.get(k, 0)

        scrapped_value = 0.0
        for k, qty in scrapped_by_part.items():
            scrapped_value += qty * cost_per_unit_map.get(k, 0)

        instock_value = total_value_all_purchases - utilized_value - scrapped_value

        return {
            'total_original_received_qty': round(original_received_qty, 2),
            'total_current_qty': round(total_current_qty, 2),
            'total_utilized_qty': round(total_utilized_qty, 2),
            'total_scrapped_qty': round(total_scrapped_qty, 2),
            'total_issued_qty': round(total_issued_qty, 2),
            'closing_stock_qty': round(closing_stock_qty, 2),
            'total_purchase_value': round(total_value_all_purchases, 2),
            'instock_value': round(instock_value, 2),
            'utilized_value': round(utilized_value, 2),
            'scrapped_value': round(scrapped_value, 2)
        }
    except Exception as e:
        print(f"Error computing stock totals: {e}")
        return {
            'total_original_received_qty': 0.0,
            'total_current_qty': 0.0,
            'total_utilized_qty': 0.0,
            'total_scrapped_qty': 0.0,
            'total_issued_qty': 0.0,
            'closing_stock_qty': 0.0,
            'total_purchase_value': 0.0,
            'instock_value': 0.0,
            'utilized_value': 0.0,
            'scrapped_value': 0.0
        }

def get_all_stock_issues():
    """Get all stock issue records"""
    try:
        response = supabase.table('stock_issue_register').select('*').order('created_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting stock issue records: {e}")
        return []

def get_all_utilization():
    """Get all material utilization records"""
    try:
        response = supabase.table('material_utilization').select('*').order('created_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting utilization records: {e}")
        return []


def save_material_utilization(util_data):
    """Save a material utilization record and return the inserted row or None."""
    try:
        # normalize numeric
        if 'quantity' in util_data and util_data['quantity'] == '':
            util_data['quantity'] = None
        elif 'quantity' in util_data and util_data['quantity'] is not None:
            util_data['quantity'] = float(util_data['quantity'])

        # ensure processed_by_id is numeric if present
        if 'processed_by_id' in util_data:
            try:
                if util_data['processed_by_id'] is None or str(util_data['processed_by_id']).strip() == '':
                    util_data.pop('processed_by_id', None)
                else:
                    util_data['processed_by_id'] = int(util_data['processed_by_id'])
            except Exception:
                # remove non-numeric processed_by_id to avoid insert type errors
                util_data.pop('processed_by_id', None)

        # normalize driver_id and mech_id to strings if present
        if 'driver_id' in util_data:
            try:
                if util_data['driver_id'] is None:
                    util_data.pop('driver_id', None)
                else:
                    util_data['driver_id'] = str(util_data['driver_id']).strip()
            except Exception:
                util_data.pop('driver_id', None)

        if 'mech_id' in util_data:
            try:
                if util_data['mech_id'] is None:
                    util_data.pop('mech_id', None)
                else:
                    util_data['mech_id'] = str(util_data['mech_id']).strip()
            except Exception:
                util_data.pop('mech_id', None)

        # If numeric processed_by_id exists, also set a readable processed_by field
        if 'processed_by_id' in util_data and util_data.get('processed_by_id') is not None:
            try:
                util_data['processed_by'] = str(util_data.get('processed_by_id'))
            except Exception:
                pass

        util_data['created_at'] = datetime.now().isoformat()
        util_data['updated_at'] = datetime.now().isoformat()

        res = supabase.table('material_utilization').insert(util_data).execute()
        try:
            print(f"[DB] Inserted material_utilization: part_no={util_data.get('part_no')} quantity={util_data.get('quantity')} res_data_present={bool(res.data)}")
            # Print full response data and any error for debugging
            try:
                print(f"[DB] material_utilization res.data: {res.data}")
            except Exception:
                pass
            try:
                print(f"[DB] material_utilization res.error: {getattr(res, 'error', None)}")
            except Exception:
                pass
        except Exception:
            pass
        # If the insert did not return row data, try to fetch the inserted row by entry_no as a fallback
        inserted_row = None
        if res.data and len(res.data) > 0:
            inserted_row = res.data[0]
        else:
            try:
                # attempt to select the row by unique entry_no we set earlier
                en = util_data.get('entry_no')
                if en:
                    sel = supabase.table('material_utilization').select('*').eq('entry_no', en).limit(1).execute()
                    if sel.data and len(sel.data) > 0:
                        inserted_row = sel.data[0]
                        print(f"[DB] Fallback select found material_utilization by entry_no={en}: {inserted_row}")
                    else:
                        print(f"[DB] Fallback select found no rows for entry_no={en}")
            except Exception as e:
                print(f"[DB] Fallback select error: {e}")

        return {'row': inserted_row, 'error': getattr(res, 'error', None)}
    except Exception as e:
        print(f"Error saving material utilization: {e}")
        import traceback
        traceback.print_exc()
        return None


def consume_part_from_purchases(part_no, qty_to_consume):
    """Consume quantity from purchases rows for a given part_no using FIFO.
    Returns list of dicts with purchase_id and consumed quantity."""
    try:
        remaining = float(qty_to_consume or 0)
        if remaining <= 0:
            return []

        # Fetch purchases ordered oldest first. Don't rely solely on a status
        # value of 'active' because some existing rows may have NULL/empty
        # status. We'll skip rows that are already marked as consumed/issued.
        print(f"[DB] consume_part_from_purchases start: part_no={part_no} qty={remaining}")
        resp = supabase.table('purchases').select('*').order('created_at', desc=False).execute()
        consumed = []
        if not resp.data:
            print("[DB] No active purchases returned for consumption")
            return consumed

        for row in resp.data:
            # skip rows that are already issued/consumed
            status_val = (row.get('status') or '')
            try:
                if status_val and status_val.lower() in ('issued', 'consumed', 'removed', 'scrapped', 'deleted'):
                    # nothing to take from rows already marked issued/consumed
                    continue
            except Exception:
                pass

            # match by part_number or part_no field
            pn = (row.get('part_number') or row.get('part_no') or '')
            pn = pn.strip() if isinstance(pn, str) else str(pn)
            if not pn:
                continue
            # match case-insensitively to avoid mismatches from casing
            try:
                if pn.lower() != str(part_no).lower():
                    continue
            except Exception:
                if pn != part_no:
                    continue

            avail = 0
            try:
                avail = float(row.get('quantity') or 0)
            except Exception:
                avail = 0

            print(f"[DB] Matching purchase row id={row.get('id')} avail={avail}")

            if avail <= 0:
                continue

            take = min(avail, remaining)
            new_qty = avail - take

            # Update purchase row with new quantity (and status if fully consumed)
            update_data = {'quantity': new_qty, 'updated_at': datetime.now().isoformat()}
            if new_qty <= 0:
                update_data['status'] = 'issued'

            res = supabase.table('purchases').update(update_data).eq('id', row.get('id')).execute()
            print(f"[DB] Updated purchase id={row.get('id')} set={update_data} result_rows={len(res.data) if getattr(res,'data',None) else 0}")

            consumed.append({'purchase_id': row.get('id'), 'consumed': take, 'remaining_in_row': new_qty})
            remaining -= take
            if remaining <= 0:
                break

        print(f"[DB] consume_part_from_purchases finished: requested={qty_to_consume} consumed_total={sum(c['consumed'] for c in consumed) if consumed else 0}")
        if not consumed:
            print(f"[DB] No purchases matched part_no={part_no} for consumption")
        return consumed
    except Exception as e:
        print(f"Error consuming part from purchases: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_all_scrap():
    """Get all scrap records"""
    try:
        response = supabase.table('scrap').select('*').order('created_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting scrap records: {e}")
        return []
