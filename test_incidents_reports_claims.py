from database import save_incidents_reports_claims

# Test data for claims
claim_entries = [
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'from_year': '2024',
        'to_year': '2025',
        'approx_date': '2024-07-20',
        'nature_of_claim': 'Insurance claim for collision damage',
        'mode_of_claim': 'Insurance settlement',
        'claim_value_responsible': 'Rs. 25,000 - Insurance Company'
    },
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'from_year': '2024',
        'to_year': '2025',
        'approx_date': '2024-11-25',
        'nature_of_claim': 'Institutional claim for tire replacement',
        'mode_of_claim': 'Personal settlement',
        'claim_value_responsible': 'Rs. 8,000 - Institution budget'
    }
]

try:
    saved_count = save_incidents_reports_claims(claim_entries)
    print(f"\n✓ SUCCESS: Saved {saved_count} claim(s) to database")
    print("\nTest Data:")
    for i, entry in enumerate(claim_entries, 1):
        print(f"\nEntry {i}:")
        print(f"  Vehicle: {entry['vehicle_id']} - {entry['registration_no']}")
        print(f"  Period: {entry['from_year']} - {entry['to_year']}")
        print(f"  Approx Date: {entry['approx_date']}")
        print(f"  Nature: {entry['nature_of_claim']}")
        print(f"  Mode: {entry['mode_of_claim']}")
        print(f"  Value: {entry['claim_value_responsible']}")
except Exception as e:
    print(f"\n✗ FAILED: Error saving claims")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
