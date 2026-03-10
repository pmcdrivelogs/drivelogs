"""
Check super admin fields in database
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

print("\n" + "="*60)
print("Checking Super Admin Data")
print("="*60 + "\n")

try:
    response = supabase.table('super_admins').select('*').execute()
    
    if response.data:
        for admin in response.data:
            print("Admin Record:")
            for key, value in admin.items():
                print(f"  {key}: {value}")
            print()
    else:
        print("No admins found")
        
except Exception as e:
    print(f"Error: {e}")
