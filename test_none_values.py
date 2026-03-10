import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Test with None values like Flask form might send
test_data = {
    'vehicle_id': 'V002',
    'registration_no': None,
    'registration_number': None,
    'route_id': None,
    'vehicle_type': None,
    'managing_college': None,
    'make': None,
    'modal': None,
    'year_manufacturing': None,
    'year_purchasing': None,
    'engine_number': None,
    'chassis_number': None,
    'speed_governer_id': None,
    'seating_capacity': None
}

print("Testing with None values...")
print(f"Vehicle ID: {test_data['vehicle_id']}")

try:
    # Convert None to empty strings
    for key, value in test_data.items():
        if value is None and key not in ['created_at', 'updated_at']:
            test_data[key] = ''
    
    # Check if record exists
    response = supabase.table('vehicle_permanent_records').select('id').eq('vehicle_id', test_data['vehicle_id']).execute()
    
    if response.data and len(response.data) > 0:
        # Update
        record_id = response.data[0]['id']
        test_data['updated_at'] = datetime.now().isoformat()
        print(f"Updating record ID: {record_id}")
        result = supabase.table('vehicle_permanent_records').update(test_data).eq('id', record_id).execute()
        print(f"✓ Update successful!")
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
