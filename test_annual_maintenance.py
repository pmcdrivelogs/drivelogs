from database import save_annual_maintenance

# Test data for annual maintenance (26 processes)
test_maintenance = {
    'vehicle_id': 'V001',
    'registration_no': 'TN01AB1234',
    'from_month': 'April',
    'to_month': 'September',
    
    # Process 1: PUMP OIL ATTACHMENT
    'processed_date_1': '2024-09-30',
    'kilometer_reading_1': '17000',
    'action_processed_1': 'Oil checked and replaced',
    'observation_1': 'Functioning properly',
    'parts_used_1': 'Pump Oil',
    'qty_1': '1L',
    'supplier_bill_1': 'BILL001/30-09-2024',
    'value_1': '₹300',
    
    # Process 2: CROWN VALIDE ADJUSTMENT
    'processed_date_2': '2024-09-30',
    'kilometer_reading_2': '17000',
    'action_processed_2': 'Adjusted crown valve',
    'observation_2': 'Working smoothly',
    'parts_used_2': 'Valve parts',
    'qty_2': '1',
    'supplier_bill_2': 'BILL002/30-09-2024',
    'value_2': '₹500',
    
    # Process 3: DRIVE LINE REPLACEMENT
    'processed_date_3': '2024-09-30',
    'kilometer_reading_3': '17000',
    'action_processed_3': 'Drive line inspected',
    'observation_3': 'No replacement needed',
    'parts_used_3': 'None',
    'qty_3': '0',
    'supplier_bill_3': 'N/A',
    'value_3': '₹0',
    
    # Process 4: CLUTCH FREE ADJUSTMENT
    'processed_date_4': '2024-09-30',
    'kilometer_reading_4': '17000',
    'action_processed_4': 'Clutch free play adjusted',
    'observation_4': 'Working properly',
    'parts_used_4': 'None',
    'qty_4': '0',
    'supplier_bill_4': 'N/A',
    'value_4': '₹0',
    
    # Process 5: PROGRESSIVE BRAKING FOR ACCIDENT
    'processed_date_5': '2024-09-30',
    'kilometer_reading_5': '17000',
    'action_processed_5': 'Braking system tested',
    'observation_5': 'Progressive braking functioning well',
    'parts_used_5': 'None',
    'qty_5': '0',
    'supplier_bill_5': 'N/A',
    'value_5': '₹0',
    
    # Process 6-26: Additional processes (simplified for test)
    'processed_date_6': '2024-09-30',
    'kilometer_reading_6': '17000',
    'action_processed_6': 'Tyre condition checked',
    'observation_6': 'Good condition',
    'parts_used_6': 'None',
    'qty_6': '0',
    'supplier_bill_6': 'N/A',
    'value_6': '₹0',
    
    'processed_date_7': '2024-09-30',
    'kilometer_reading_7': '17000',
    'action_processed_7': 'Brake oil checked',
    'observation_7': 'Level normal',
    'parts_used_7': 'Brake oil',
    'qty_7': '0.5L',
    'supplier_bill_7': 'BILL003/30-09-2024',
    'value_7': '₹200',
}

# Fill remaining processes 8-26 with minimal data
for i in range(8, 27):
    test_maintenance[f'processed_date_{i}'] = '2024-09-30'
    test_maintenance[f'kilometer_reading_{i}'] = '17000'
    test_maintenance[f'action_processed_{i}'] = f'Process {i} completed'
    test_maintenance[f'observation_{i}'] = 'Checked and verified'
    test_maintenance[f'parts_used_{i}'] = 'None'
    test_maintenance[f'qty_{i}'] = '0'
    test_maintenance[f'supplier_bill_{i}'] = 'N/A'
    test_maintenance[f'value_{i}'] = '₹0'

print("Testing Annual Maintenance Save Function...")
print("=" * 60)

saved_count = save_annual_maintenance(test_maintenance)

if saved_count > 0:
    print(f"\n✓ SUCCESS: Saved {saved_count} annual maintenance record!")
    print(f"Vehicle ID: {test_maintenance['vehicle_id']}")
    print(f"Registration No: {test_maintenance['registration_no']}")
    print(f"Period: {test_maintenance['from_month']} to {test_maintenance['to_month']}")
    print(f"Processes completed: 26")
else:
    print("\n✗ FAILED: Could not save annual maintenance record")
    print("Check the error messages above for details")

print("=" * 60)
