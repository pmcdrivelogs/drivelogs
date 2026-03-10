import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Simulate exact form submission
test_data = {
    'vehicle_id': 'V003',
    'registration_no': 'TN-99-ZZ-9999',
    'registration_number': 'TN-99-ZZ-9999',
    'route_id': 'R999',
    'vehicle_type': 'BUS',
    'managing_college': 'Test College',
    'make': 'TATA',
    'modal': 'LP 410',
    'year_manufacturing': '2024',
    'year_purchasing': '2024',
    'engine_number': 'ENG999',
    'chassis_number': 'CHS999',
    'speed_governer_id': 'SG999',
    'seating_capacity': '50'
}

print("Testing complete form submission...")
print(f"Vehicle ID: {test_data['vehicle_id']}")

try:
    # Convert None to empty strings (like the fixed database.py does)
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
    
    print(f"\n✅ SUCCESS! Record saved to database")
    print(f"Vehicle ID: {result.data[0]['vehicle_id']}")
    print(f"Registration: {result.data[0]['registration_number']}")
    print(f"Route ID: {result.data[0]['route_id']}")
    print(f"Managing College: {result.data[0]['managing_college']}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
