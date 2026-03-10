from database import save_annual_summary_recommendations

# Test data for annual summary recommendations
recommendation_entries = [
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'recommendation_year': '2025',
        'approx_date': '2025-06-01',
        'anticipated_complaint': 'Brake system may require replacement due to wear',
        'prevention': 'Schedule brake inspection and replacement in May 2025',
        'remarks': 'Based on current usage patterns and last replacement date'
    },
    {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'recommendation_year': '2025',
        'approx_date': '2025-09-01',
        'anticipated_complaint': 'Battery replacement may be needed',
        'prevention': 'Monitor battery health and replace if voltage drops below threshold',
        'remarks': 'Battery installed 3 years ago, approaching end of life'
    }
]

try:
    saved_count = save_annual_summary_recommendations(recommendation_entries)
    print(f"\n✓ SUCCESS: Saved {saved_count} annual summary recommendation(s) to database")
    print("\nTest Data:")
    for i, entry in enumerate(recommendation_entries, 1):
        print(f"\nEntry {i}:")
        print(f"  Vehicle: {entry['vehicle_id']} - {entry['registration_no']}")
        print(f"  Year: {entry['recommendation_year']}")
        print(f"  Approx Date: {entry['approx_date']}")
        print(f"  Anticipated Complaint: {entry['anticipated_complaint']}")
        print(f"  Prevention: {entry['prevention']}")
        print(f"  Remarks: {entry['remarks']}")
except Exception as e:
    print(f"\n✗ FAILED: Error saving annual summary recommendations")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
