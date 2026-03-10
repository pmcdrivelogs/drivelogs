from database import save_incidents_reports_incidents

# Test data for incidents
incident_entries = [
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'from_year': '2024',
        'to_year': '2025',
        'date': '2024-07-15',
        'nature_of_incident': 'Minor collision at parking area',
        'reasons_causes': 'Poor visibility due to heavy rain',
        'responsible': 'Driver - John Doe'
    },
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'from_year': '2024',
        'to_year': '2025',
        'date': '2024-11-20',
        'nature_of_incident': 'Tire burst on highway',
        'reasons_causes': 'Worn out tire not replaced on time',
        'responsible': 'Maintenance team oversight'
    }
]

try:
    saved_count = save_incidents_reports_incidents(incident_entries)
    print(f"\n✓ SUCCESS: Saved {saved_count} incident(s) to database")
    print("\nTest Data:")
    for i, entry in enumerate(incident_entries, 1):
        print(f"\nEntry {i}:")
        print(f"  Vehicle: {entry['vehicle_id']} - {entry['registration_no']}")
        print(f"  Period: {entry['from_year']} - {entry['to_year']}")
        print(f"  Date: {entry['date']}")
        print(f"  Nature: {entry['nature_of_incident']}")
        print(f"  Reasons: {entry['reasons_causes']}")
        print(f"  Responsible: {entry['responsible']}")
except Exception as e:
    print(f"\n✗ FAILED: Error saving incidents")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
