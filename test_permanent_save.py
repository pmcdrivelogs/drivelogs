import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

# Test data matching the form
test_data = {
    'vehicle_id': 'V001',
    'registration_no': 'TN-01-AB-1234',
    'registration_number': 'TN-01-AB-1234',
    'route_id': 'R001',
    'vehicle_type': 'Bus',
    'managing_college': 'PSG College of Technology',
    'make': 'Ashok Leyland',
    'modal': 'Viking',
    'year_manufacturing': '2020',
    'year_purchasing': '2020',
    'engine_number': 'AL12345',
    'chassis_number': 'CH67890',
    'speed_governer_id': 'SG001',
    'seating_capacity': '40'
}

print("Testing vehicle permanent record save...")
print(f"Vehicle ID: {test_data['vehicle_id']}")

try:
    # Check if record exists
    response = supabase.table('vehicle_permanent_records').select('id').eq('vehicle_id', test_data['vehicle_id']).execute()
    
    if response.data and len(response.data) > 0:
        # Update
        record_id = response.data[0]['id']
        test_data['updated_at'] = datetime.now().isoformat()
        result = supabase.table('vehicle_permanent_records').update(test_data).eq('id', record_id).execute()
        print(f"✓ Updated existing record (ID: {record_id})")
    else:
        # Insert
        test_data['created_at'] = datetime.now().isoformat()
        test_data['updated_at'] = datetime.now().isoformat()
        result = supabase.table('vehicle_permanent_records').insert(test_data).execute()
        print(f"✓ Inserted new record")
    
    print(f"✓ Save successful!")
    print(f"Result: {result.data}")
    
except Exception as e:
    print(f"✗ Error: {e}")
