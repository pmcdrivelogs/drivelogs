"""
Test script for utilization record submission
"""
from database import save_utilization_record
from datetime import datetime, date

def test_utilization_save():
    """Test saving multiple utilization record entries"""
    print("\n" + "="*70)
    print("Testing Utilization Record Save")
    print("="*70)
    
    # Create sample utilization entries
    test_entries = [
        {
            'vehicle_id': 'V001',
            'registration_no': 'TN01AB1234',
            'opening_time': date.today().isoformat(),
            'opening_kilometer': '50000',
            'opening_place': 'PMC College',
            'purpose_trip': 'Student Transport - Morning',
            'strength_she': '45',
            'strength_he': '30',
            'closing_time': '09:30:00',
            'closing_kilometer': '50085',
            'closing_place': 'PMC College',
            'coverage_time': '2:30',
            'coverage_kms': '85'
        },
        {
            'vehicle_id': 'V001',
            'registration_no': 'TN01AB1234',
            'opening_time': date.today().isoformat(),
            'opening_kilometer': '50085',
            'opening_place': 'PMC College',
            'purpose_trip': 'Student Transport - Evening',
            'strength_she': '48',
            'strength_he': '32',
            'closing_time': '17:30:00',
            'closing_kilometer': '50175',
            'closing_place': 'PMC College',
            'coverage_time': '7:45',
            'coverage_kms': '90'
        }
    ]
    
    print(f"\nAttempting to save {len(test_entries)} utilization records...")
    
    saved_count = save_utilization_record(test_entries)
    
    if saved_count > 0:
        print(f"✓ SUCCESS: Saved {saved_count} utilization record(s)")
        print("\nTest Data:")
        for i, entry in enumerate(test_entries, 1):
            print(f"\n  Entry {i}:")
            print(f"    Vehicle: {entry['vehicle_id']} - {entry['registration_no']}")
            print(f"    Opening: {entry['opening_time']} @ {entry['opening_place']} - {entry['opening_kilometer']} km")
            print(f"    Purpose: {entry['purpose_trip']}")
            print(f"    Strength: {entry['strength_she']} female, {entry['strength_he']} male")
            print(f"    Closing: {entry['closing_time']} @ {entry['closing_place']} - {entry['closing_kilometer']} km")
            print(f"    Coverage: {entry['coverage_time']} hrs, {entry['coverage_kms']} kms")
    else:
        print("✗ FAILED: Could not save utilization records")
        print("Check the console for error messages")
    
    print("\n" + "="*70)
    print("Test Complete")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_utilization_save()
