"""
Test script for daily technical remarks submission
"""
from database import save_daily_technical_remarks
from datetime import datetime, date

def test_technical_remarks_save():
    """Test saving multiple daily technical remarks entries"""
    print("\n" + "="*70)
    print("Testing Daily Technical Remarks Save")
    print("="*70)
    
    # Create sample technical remarks entries
    test_entries = [
        {
            'vehicle_id': 'V001',
            'registration_no': 'TN01AB1234',
            'date': date.today().isoformat(),
            'kilometer': '50000',
            'drivers_voice': 'No work',
            'technical_observation': 'Regular inspection completed. All systems working properly.',
            'day_end_status': 'Arrested',
            'materials_purchased': 'Engine oil, Air filter',
            'supplier_bill': 'ABC Parts/BILL001/17-12-2025',
            'amount': '2500'
        },
        {
            'vehicle_id': 'V001',
            'registration_no': 'TN01AB1234',
            'date': date.today().isoformat(),
            'kilometer': '50180',
            'drivers_voice': 'Minor brake noise observed',
            'technical_observation': 'Checked brake pads and adjusted. Issue resolved.',
            'day_end_status': 'Arrested',
            'materials_purchased': 'Brake lubricant',
            'supplier_bill': 'XYZ Auto/BILL102/17-12-2025',
            'amount': '350'
        }
    ]
    
    print(f"\nAttempting to save {len(test_entries)} technical remarks...")
    
    saved_count = save_daily_technical_remarks(test_entries)
    
    if saved_count > 0:
        print(f"✓ SUCCESS: Saved {saved_count} technical remark(s)")
        print("\nTest Data:")
        for i, entry in enumerate(test_entries, 1):
            print(f"\n  Entry {i}:")
            print(f"    Vehicle: {entry['vehicle_id']} - {entry['registration_no']}")
            print(f"    Date: {entry['date']}, KM: {entry['kilometer']}")
            print(f"    Driver's Voice: {entry['drivers_voice']}")
            print(f"    Observation: {entry['technical_observation']}")
            print(f"    Status: {entry['day_end_status']}")
            print(f"    Materials: {entry['materials_purchased']}")
            print(f"    Supplier: {entry['supplier_bill']}")
            print(f"    Amount: ₹{entry['amount']}")
    else:
        print("✗ FAILED: Could not save technical remarks")
        print("Check the console for error messages")
    
    print("\n" + "="*70)
    print("Test Complete")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_technical_remarks_save()
