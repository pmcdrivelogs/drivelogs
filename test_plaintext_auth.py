#!/usr/bin/env python
"""Test plaintext password matching"""
import os
from dotenv import load_dotenv
load_dotenv()

from database import authenticate_user

# Test with correct plaintext passwords
print("Testing plaintext password authentication:")
print()

# Test 1: admin@gmail.com with password "admin123"
result = authenticate_user("admin@gmail.com", "admin123")
print(f"Test 1: authenticate_user('admin@gmail.com', 'admin123')")
print(f"Result: {result}")
print()

# Test 2: user1@pmctech.org with password "user1@pmctech"
result = authenticate_user("user1@pmctech.org", "user1@pmctech")
print(f"Test 2: authenticate_user('user1@pmctech.org', 'user1@pmctech')")
print(f"Result: {result}")
print()

# Test 3: Check super admin
from database import authenticate_super_admin
result = authenticate_super_admin("Rahul", "Admin@123")
print(f"Test 3: authenticate_super_admin('Rahul', 'Admin@123')")
print(f"Result: {result}")
