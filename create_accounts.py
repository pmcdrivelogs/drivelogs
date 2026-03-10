"""
Create initial admin and user accounts for Drive Logs
Run this after setting up the database tables
"""

import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from supabase import create_client, Client

load_dotenv()

# Initialize Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def create_admin(username, password, full_name, email=None):
    """Create a super admin account"""
    try:
        password_hash = generate_password_hash(password)
        data = {
            'username': username,
            'password_hash': password_hash,
            'full_name': full_name,
            'email': email,
            'is_active': True
        }
        
        result = supabase.table('super_admins').insert(data).execute()
        print(f"✓ Super Admin created successfully: {username}")
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"✗ Error creating admin: {e}")
        return None

def create_user(email, password, full_name, department=None):
    """Create a regular user account"""
    try:
        password_hash = generate_password_hash(password)
        data = {
            'email': email,
            'password_hash': password_hash,
            'full_name': full_name,
            'department': department,
            'role': 'user',
            'is_active': True
        }
        
        result = supabase.table('users').insert(data).execute()
        print(f"✓ User created successfully: {email}")
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"✗ Error creating user: {e}")
        return None

def main():
    print("\n" + "="*60)
    print("Drive Logs - Create Initial Accounts")
    print("="*60 + "\n")
    
    # Create Super Admin
    print("Creating Super Admin...")
    create_admin(
        username='admin',
        password='admin123',
        full_name='Super Administrator',
        email='admin@drivelogs.com'
    )
    
    # Create Test User
    print("\nCreating Test User...")
    create_user(
        email='test@example.com',
        password='password123',
        full_name='Test User',
        department='Transport'
    )
    
    print("\n" + "="*60)
    print("Account Creation Complete!")
    print("="*60)
    print("\nLogin Credentials:")
    print("\nSuper Admin:")
    print("  Username: admin")
    print("  Password: admin123")
    print("\nRegular User:")
    print("  Email: test@example.com")
    print("  Password: password123")
    print("\n" + "="*60 + "\n")
    
    print("⚠️  IMPORTANT: Change these passwords in production!")
    print("")

if __name__ == "__main__":
    main()
