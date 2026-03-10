"""Test script for process of works"""
from database import save_process_of_works

# Test data
test_entries = [
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'date': '2024-01-15',
        'time': '14:30:00',
        'nature_of_work': 'Engine oil change',
        'rectified_results': 'Oil changed successfully',
        'bill_no': 'BILL001',
        'amount': '₹1500'
    },
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'date': '2024-01-16',
        'time': '10:00:00',
        'nature_of_work': 'Brake pad replacement',
        'rectified_results': 'Brake pads replaced, tested OK',
        'bill_no': 'BILL002',
        'amount': '₹3500'
    }
]

# Test the save function
print("Testing save_process_of_works...")
print(f"Attempting to save {len(test_entries)} process of works records...")

result = save_process_of_works(test_entries)

print(f"\n{'='*60}")
if result == len(test_entries):
    print(f"✓ SUCCESS: Saved {result} process of works record(s)")
else:
    print(f"✗ PARTIAL: Saved {result} out of {len(test_entries)} records")
print(f"{'='*60}\n")
