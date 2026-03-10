from database import save_feedback

# Test data for feedback
feedback_data = {
    'name': 'John Doe',
    'email': 'john.doe@example.com',
    'contact': '9876543210',
    'department': 'Maintenance Department',
    'feedback_type': 'Suggestion',
    'subject': 'Improve dashboard interface',
    'message': 'The dashboard could benefit from a more intuitive layout with better visibility of critical alerts. Perhaps adding a color-coded system for urgent issues would help.',
    'rating': 4
}

try:
    saved_count = save_feedback(feedback_data)
    print(f"\n✓ SUCCESS: Saved feedback to database")
    print("\nTest Data:")
    print(f"  Name: {feedback_data['name']}")
    print(f"  Email: {feedback_data['email']}")
    print(f"  Contact: {feedback_data['contact']}")
    print(f"  Department: {feedback_data['department']}")
    print(f"  Type: {feedback_data['feedback_type']}")
    print(f"  Subject: {feedback_data['subject']}")
    print(f"  Message: {feedback_data['message']}")
    print(f"  Rating: {feedback_data['rating']}/5 stars")
except Exception as e:
    print(f"\n✗ FAILED: Error saving feedback")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
