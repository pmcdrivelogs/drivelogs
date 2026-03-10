"""
Mock database for testing without Supabase
This file simulates database operations for development/testing
"""

from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

# Mock data - In-memory storage
MOCK_USERS = {
    'test@example.com': {
        'id': '1',
        'email': 'test@example.com',
        'password_hash': generate_password_hash('password123'),
        'full_name': 'Test User',
        'role': 'user',
        'is_active': True
    }
}

MOCK_ADMINS = {
    'admin': {
        'id': '1',
        'username': 'admin',
        'password_hash': generate_password_hash('admin123'),
        'full_name': 'Super Admin',
        'is_active': True
    }
}

LOGIN_LOGS = []

def authenticate_user(email, password):
    """Authenticate a regular user"""
    user = MOCK_USERS.get(email)
    if user and user['is_active']:
        if check_password_hash(user['password_hash'], password):
            return user
    return None

def authenticate_super_admin(username, password):
    """Authenticate a super admin user"""
    admin = MOCK_ADMINS.get(username)
    if admin and admin['is_active']:
        if check_password_hash(admin['password_hash'], password):
            return admin
    return None

def log_login_attempt(identifier, success, ip_address):
    """Log login attempts"""
    LOGIN_LOGS.append({
        'user_identifier': identifier,
        'success': success,
        'ip_address': ip_address,
        'timestamp': datetime.now().isoformat()
    })
    print(f"Login attempt: {identifier} - {'Success' if success else 'Failed'}")

def create_user(email, password, full_name, role='user'):
    """Create a new user"""
    if email in MOCK_USERS:
        return None
    password_hash = generate_password_hash(password)
    user = {
        'id': str(len(MOCK_USERS) + 1),
        'email': email,
        'password_hash': password_hash,
        'full_name': full_name,
        'role': role,
        'is_active': True,
        'created_at': datetime.now().isoformat()
    }
    MOCK_USERS[email] = user
    return user

def create_super_admin(username, password, full_name):
    """Create a new super admin"""
    if username in MOCK_ADMINS:
        return None
    password_hash = generate_password_hash(password)
    admin = {
        'id': str(len(MOCK_ADMINS) + 1),
        'username': username,
        'password_hash': password_hash,
        'full_name': full_name,
        'is_active': True,
        'created_at': datetime.now().isoformat()
    }
    MOCK_ADMINS[username] = admin
    return admin

def get_all_users():
    """Get all users"""
    return list(MOCK_USERS.values())

def update_user_status(user_id, is_active):
    """Update user active status"""
    for user in MOCK_USERS.values():
        if user['id'] == user_id:
            user['is_active'] = is_active
            return user
    return None

# Print mock credentials on import
print("\n" + "="*60)
print("MOCK DATABASE LOADED - For Testing Only")
print("="*60)
print("Test User Login:")
print("  Email: test@example.com")
print("  Password: password123")
print("\nSuper Admin Login:")
print("  Username: admin")
print("  Password: admin123")
print("="*60 + "\n")
