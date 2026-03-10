#!/usr/bin/env python
"""Local authentication diagnostic test"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Test 1: Check env vars
print("=" * 60)
print("STEP 1: Check environment variables")
print("=" * 60)
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
print(f"SUPABASE_URL: {url}")
print(f"SUPABASE_KEY: {key[:20]}..." if key else "SUPABASE_KEY: NOT SET")
print()

# Test 2: Import and init Supabase
print("=" * 60)
print("STEP 2: Initialize Supabase client")
print("=" * 60)
try:
    from database import supabase
    print("✓ Supabase proxy imported successfully")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 3: Query users table
print("=" * 60)
print("STEP 3: Query users table (first 3 records)")
print("=" * 60)
try:
    resp = supabase.table('users').select('id,email,password,is_active').limit(3).execute()
    if resp.data:
        print(f"✓ Found {len(resp.data)} user(s):")
        for user in resp.data:
            pwd = user.get('password', '')
            pwd_preview = f"{pwd[:20]}..." if len(pwd) > 20 else pwd
            print(f"  - email: {user.get('email')}, is_active: {user.get('is_active')}, password format: {pwd_preview}")
    else:
        print("✗ No users found in database!")
except Exception as e:
    print(f"✗ Query failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test authentication
print()
print("=" * 60)
print("STEP 4: Test authentication with first user")
print("=" * 60)
try:
    from database import authenticate_user, authenticate_super_admin
    
    if resp.data:
        test_user = resp.data[0]
        test_email = test_user.get('email')
        print(f"Testing with email: {test_email}")
        print("Note: Password must match what's stored. If you know the password, enter it below.")
        
        # Attempt with empty password first (for diagnostics)
        result = authenticate_user(test_email, "test123")
        print(f"Result of authenticate_user('{test_email}', 'test123'): {result}")
        
except Exception as e:
    print(f"✗ Auth test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Check admin table
print()
print("=" * 60)
print("STEP 5: Query super_admins table (first 3 records)")
print("=" * 60)
try:
    resp_admin = supabase.table('super_admins').select('id,email,username,password,is_active').limit(3).execute()
    if resp_admin.data:
        print(f"✓ Found {len(resp_admin.data)} admin(s):")
        for admin in resp_admin.data:
            pwd = admin.get('password', '')
            pwd_preview = f"{pwd[:20]}..." if len(pwd) > 20 else pwd
            print(f"  - email: {admin.get('email')}, username: {admin.get('username')}, is_active: {admin.get('is_active')}, password format: {pwd_preview}")
    else:
        print("✗ No admins found in database!")
except Exception as e:
    print(f"✗ Query failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("Diagnostic test complete.")
print("=" * 60)
