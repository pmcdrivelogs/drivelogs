"""
Test script for trip opening checklist submission
"""
from database import save_trip_opening_checklist
from datetime import datetime, date

def test_trip_checklist_save():
    """Test saving multiple trip checklist entries"""
    print("\n" + "="*70)
    print("Testing Trip Opening Checklist Save")
    print("="*70)
    
    # Create sample checklist entries
    test_entries = [
        {
            'vehicle_id': 'V001',
            'registration_no': 'TN01AB1234',
            'check_date': date.today().isoformat(),
            'check_time': '08:00:00',
            'driver_name': 'John Doe',
            'kilometer_reading': '50000',
            'fuel_level': 'Ok',
            'engine_oil_level': 'Ok',
            'radiator_water_level': 'Ok',
            'vacuum_level': 'Ok',
            'tyre_front_left': 'Ok',
            'tyre_front_right': 'Ok',
            'tyre_rear_lin': 'Ok',
            'tyre_rear_lout': 'Ok',
            'tyre_rear_rin': 'Ok',
            'tyre_rear_rout': 'Ok',
            'cleanliness_glass': 'Ok',
            'remarks': 'All systems normal'
        },
        {
            'vehicle_id': 'V001',
            'registration_no': 'TN01AB1234',
            'check_date': date.today().isoformat(),
            'check_time': '14:00:00',
            'driver_name': 'Jane Smith',
            'kilometer_reading': '50150',
            'fuel_level': 'Ok',
            'engine_oil_level': 'Ok',
            'radiator_water_level': 'Ok',
            'vacuum_level': 'Ok',
            'tyre_front_left': 'Ok',
            'tyre_front_right': 'Ok',
            'tyre_rear_lin': 'Ok',
            'tyre_rear_lout': 'Ok',
            'tyre_rear_rin': 'Ok',
            'tyre_rear_rout': 'Ok',
            'cleanliness_glass': 'Ok',
            'remarks': 'Pre-afternoon trip check'
        }
    ]
    
    print(f"\nAttempting to save {len(test_entries)} checklist entries...")
    
    saved_count = save_trip_opening_checklist(test_entries)
    
    if saved_count > 0:
        print(f"✓ SUCCESS: Saved {saved_count} checklist entry(ies)")
        print("\nTest Data:")
        for i, entry in enumerate(test_entries, 1):
            print(f"\n  Entry {i}:")
            print(f"    Vehicle: {entry['vehicle_id']} - {entry['registration_no']}")
            print(f"    Date/Time: {entry['check_date']} {entry['check_time']}")
            print(f"    Driver: {entry['driver_name']}")
            print(f"    Kilometer: {entry['kilometer_reading']}")
            print(f"    Remarks: {entry['remarks']}")
    else:
        print("✗ FAILED: Could not save checklist entries")
        print("Check the console for error messages")
    
    print("\n" + "="*70)
    print("Test Complete")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_trip_checklist_save()
