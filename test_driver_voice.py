"""Test script for driver voice"""
from database import save_driver_voice

# Test data
test_entries = [
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'date': '2024-01-15',
        'time': '10:30:00',
        'complaints': 'Engine making unusual noise',
        'suggestions': 'Check engine immediately',
        'driver_name': 'John Doe'
    },
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'date': '2024-01-16',
        'time': '14:45:00',
        'complaints': 'Brake pedal feels soft',
        'suggestions': 'Inspect brake fluid level',
        'driver_name': 'John Doe'
    }
]

# Test the save function
print("Testing save_driver_voice...")
print(f"Attempting to save {len(test_entries)} driver voice records...")

result = save_driver_voice(test_entries)

print(f"\n{'='*60}")
if result == len(test_entries):
    print(f"✓ SUCCESS: Saved {result} driver voice record(s)")
else:
    print(f"✗ PARTIAL: Saved {result} out of {len(test_entries)} records")
print(f"{'='*60}\n")
