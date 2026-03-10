"""
Test database connection and authentication
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Initialize Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

print("\n" + "="*60)
print("Testing Supabase Connection")
print("="*60)

# Test connection by fetching users
try:
    print("\n1. Testing connection to users table...")
    response = supabase.table('users').select('email, full_name, role').execute()
    print(f"✓ Connection successful!")
    print(f"  Found {len(response.data)} users in database")
    
    if response.data:
        print("\n  Users:")
        for user in response.data:
            print(f"    - {user['email']} ({user['full_name']}) - Role: {user['role']}")
    
except Exception as e:
    print(f"✗ Error connecting to users table: {e}")

# Test super_admins table
try:
    print("\n2. Testing connection to super_admins table...")
    response = supabase.table('super_admins').select('username, full_name').execute()
    print(f"✓ Connection successful!")
    print(f"  Found {len(response.data)} admins in database")
    
    if response.data:
        print("\n  Admins:")
        for admin in response.data:
            print(f"    - {admin['username']} ({admin['full_name']})")
    
except Exception as e:
    print(f"✗ Error connecting to super_admins table: {e}")

# Test authentication functions
print("\n" + "="*60)
print("Testing Authentication Functions")
print("="*60)

from database import authenticate_user, authenticate_super_admin

# Test user authentication
print("\n3. Testing user authentication...")
try:
    # Get first user from database
    users = supabase.table('users').select('email, password').limit(1).execute()
    if users.data:
        test_email = users.data[0]['email']
        test_password = users.data[0]['password']
        
        user = authenticate_user(test_email, test_password)
        if user:
            print(f"✓ User authentication working!")
            print(f"  Logged in as: {user['full_name']} ({user['email']})")
        else:
            print(f"✗ Authentication failed")
    else:
        print("  No users found in database")
except Exception as e:
    print(f"✗ Error: {e}")

# Test admin authentication
print("\n4. Testing admin authentication...")
try:
    # Get first admin from database
    admins = supabase.table('super_admins').select('username, password').limit(1).execute()
    if admins.data:
        test_username = admins.data[0]['username']
        test_password = admins.data[0]['password']
        
        admin = authenticate_super_admin(test_username, test_password)
        if admin:
            print(f"✓ Admin authentication working!")
            print(f"  Logged in as: {admin['full_name']} ({admin['username']})")
        else:
            print(f"✗ Authentication failed")
    else:
        print("  No admins found in database")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "="*60)
print("Test Complete!")
print("="*60 + "\n")
