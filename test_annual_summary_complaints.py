from database import save_annual_summary_complaints

# Test data for annual summary complaints
complaint_entries = [
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'from_year': '2024',
        'to_year': '2025',
        'date': '2024-06-15',
        'complaint': 'Engine overheating issue during long trips',
        'action_taken': 'Radiator replaced and coolant system flushed',
        'status': 'Processed - Issue resolved completely'
    },
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'from_year': '2024',
        'to_year': '2025',
        'date': '2024-09-20',
        'complaint': 'Brake pad wear noticed during inspection',
        'action_taken': 'Brake pads replaced on all four wheels',
        'status': 'Processed - Braking performance restored'
    }
]

print("Testing Annual Summary Complaints Save Function...")
print("=" * 60)

saved_count = save_annual_summary_complaints(complaint_entries)

if saved_count > 0:
    print(f"\n✓ SUCCESS: Saved {saved_count} annual summary complaint(s)!")
    print(f"Vehicle ID: {complaint_entries[0]['vehicle_id']}")
    print(f"Registration No: {complaint_entries[0]['registration_no']}")
    print(f"Year Period: {complaint_entries[0]['from_year']} to {complaint_entries[0]['to_year']}")
    print(f"\nComplaint 1: {complaint_entries[0]['complaint']}")
    print(f"Status: {complaint_entries[0]['status']}")
    print(f"\nComplaint 2: {complaint_entries[1]['complaint']}")
    print(f"Status: {complaint_entries[1]['status']}")
else:
    print("\n✗ FAILED: Could not save annual summary complaints")
    print("Check the error messages above for details")

print("=" * 60)
