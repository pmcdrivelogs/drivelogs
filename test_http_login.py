#!/usr/bin/env python
"""Test login endpoints via HTTP"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

print("=" * 60)
print("Testing User Login Endpoint")
print("=" * 60)

# Test 1: User login with correct credentials
test_cases = [
    {
        "name": "User Login - admin@gmail.com",
        "endpoint": "/login",
        "data": {"email": "admin@gmail.com", "password": "admin123"}
    },
    {
        "name": "User Login - user1@pmctech.org",
        "endpoint": "/login",
        "data": {"email": "user1@pmctech.org", "password": "user1@pmctech"}
    },
    {
        "name": "Admin Login - Rahul",
        "endpoint": "/super-admin-login",
        "data": {"email": "Rahul", "password": "Admin@123"}
    },
    {
        "name": "Admin Login - admin@pmctech.org",
        "endpoint": "/super-admin-login",
        "data": {"email": "admin@pmctech.org", "password": "Admin@123"}
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\nTest {i}: {test['name']}")
    print(f"Endpoint: POST {test['endpoint']}")
    print(f"Data: {test['data']}")
    
    try:
        session = requests.Session()
        response = session.post(f"{BASE_URL}{test['endpoint']}", data=test['data'], allow_redirects=False)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        # Check if redirected to dashboard (success)
        if response.status_code in [302, 303]:
            print(f"Redirect Location: {response.headers.get('Location')}")
            print("✓ LOGIN SUCCESSFUL (redirected to dashboard)")
        else:
            print(f"Response Text (first 200 chars): {response.text[:200]}")
            if "Invalid email or password" in response.text or "Invalid admin credentials" in response.text:
                print("✗ LOGIN FAILED (invalid credentials message in response)")
            else:
                print("? LOGIN UNCLEAR (check response above)")
    except Exception as e:
        print(f"✗ ERROR: {e}")

print("\n" + "=" * 60)
print("Test complete")
print("=" * 60)
