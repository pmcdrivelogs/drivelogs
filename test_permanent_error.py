import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Test submitting empty data like the form might send
test_data = {
    'vehicle_id': 'V001',
    'registration_no': '',
    'registration_number': '',
    'route_id': '',
    'vehicle_type': '',
    'managing_college': '',
    'make': '',
    'modal': '',
    'year_manufacturing': '',
    'year_purchasing': '',
    'engine_number': '',
    'chassis_number': '',
    'speed_governer_id': '',
    'seating_capacity': ''
}

print("Testing with minimal data (empty strings)...")
print(f"Vehicle ID: {test_data['vehicle_id']}")

try:
    # Check if record exists
    response = supabase.table('vehicle_permanent_records').select('id').eq('vehicle_id', test_data['vehicle_id']).execute()
    
    if response.data and len(response.data) > 0:
        # Update
        record_id = response.data[0]['id']
        test_data['updated_at'] = datetime.now().isoformat()
        print(f"Updating record ID: {record_id}")
        result = supabase.table('vehicle_permanent_records').update(test_data).eq('id', record_id).execute()
        print(f"✓ Update successful!")
        print(f"Result: {result.data}")
    else:
        # Insert
        print("Creating new record...")
        test_data['created_at'] = datetime.now().isoformat()
        test_data['updated_at'] = datetime.now().isoformat()
        result = supabase.table('vehicle_permanent_records').insert(test_data).execute()
        print(f"✓ Insert successful!")
        print(f"Result: {result.data}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
