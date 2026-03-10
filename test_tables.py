import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print(f"Connecting to: {url}")

try:
    supabase = create_client(url, key)
    print("✓ Supabase client created successfully")
    
    # Test connection by listing tables
    print("\nTesting table access...")
    
    # Test vehicles table
    try:
        response = supabase.table('vehicles').select('*').limit(1).execute()
        print(f"✓ vehicles table: {len(response.data)} rows found")
    except Exception as e:
        print(f"✗ vehicles table error: {e}")
    
    # Test vehicle_annual_records table
    try:
        response = supabase.table('vehicle_annual_records').select('*').limit(1).execute()
        print(f"✓ vehicle_annual_records table: {len(response.data)} rows found")
    except Exception as e:
        print(f"✗ vehicle_annual_records table error: {e}")
    
    # Test vehicle_permanent_records table
    try:
        response = supabase.table('vehicle_permanent_records').select('*').limit(1).execute()
        print(f"✓ vehicle_permanent_records table: {len(response.data)} rows found")
    except Exception as e:
        print(f"✗ vehicle_permanent_records table error: {e}")
        
    print("\n✓ All tests completed")
    
except Exception as e:
    print(f"✗ Error: {e}")
