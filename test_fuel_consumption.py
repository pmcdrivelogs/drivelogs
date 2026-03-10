"""
Test script for fuel consumption submission
"""
from database import save_fuel_consumption
from datetime import datetime, date

def test_fuel_consumption_save():
    """Test saving multiple fuel consumption entries"""
    print("\n" + "="*70)
    print("Testing Fuel Consumption Save")
    print("="*70)
    
    # Create sample fuel consumption entries
    test_entries = [
        {
            'registration_no': 'TN01AB1234',
            'route_id': 'R001',
            'make_model': 'Tata Starbus',
            'intend_no': '1',
            'date': date.today().isoformat(),
            'bill_no': 'BILL2025001',
            'bill_date': date.today().isoformat(),
            'bunk_name': 'Indian Oil Petrol Pump',
            'qty': '50',
            'rate': '102.50',
            'amount': '5125',
            'km_reading': '50000',
            'driver_name': 'John Doe',
            'remarks': 'Regular refill'
        },
        {
            'registration_no': 'TN01AB1234',
            'route_id': 'R001',
            'make_model': 'Tata Starbus',
            'intend_no': '2',
            'date': date.today().isoformat(),
            'bill_no': 'BILL2025002',
            'bill_date': date.today().isoformat(),
            'bunk_name': 'Bharat Petroleum',
            'qty': '45',
            'rate': '103.00',
            'amount': '4635',
            'km_reading': '50180',
            'driver_name': 'Jane Smith',
            'remarks': 'Evening refill'
        }
    ]
    
    print(f"\nAttempting to save {len(test_entries)} fuel consumption records...")
    
    saved_count = save_fuel_consumption(test_entries)
    
    if saved_count > 0:
        print(f"✓ SUCCESS: Saved {saved_count} fuel consumption record(s)")
        print("\nTest Data:")
        for i, entry in enumerate(test_entries, 1):
            print(f"\n  Entry {i}:")
            print(f"    Vehicle: {entry['registration_no']} - {entry['make_model']}")
            print(f"    Date: {entry['date']}")
            print(f"    Bill: {entry['bill_no']} (Date: {entry['bill_date']})")
            print(f"    Bunk: {entry['bunk_name']}")
            print(f"    Qty: {entry['qty']} liters @ ₹{entry['rate']} = ₹{entry['amount']}")
            print(f"    KM Reading: {entry['km_reading']}")
            print(f"    Driver: {entry['driver_name']}")
            print(f"    Remarks: {entry['remarks']}")
    else:
        print("✗ FAILED: Could not save fuel consumption records")
        print("Check the console for error messages")
    
    print("\n" + "="*70)
    print("Test Complete")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_fuel_consumption_save()
