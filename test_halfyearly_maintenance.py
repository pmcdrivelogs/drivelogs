from database import save_halfyearly_maintenance

# Test data for half-yearly maintenance
test_maintenance = {
    'vehicle_id': 'V001',
    'registration_no': 'TN01AB1234',
    'from_month': 'April',
    'to_month': 'September',
    
    # Process 1: FUEL PUMP OIL CHECKUP
    'processed_date_1': '2024-09-15',
    'kilometer_reading_1': '17000',
    'action_processed_1': 'Checked and topped up',
    'observation_1': 'Oil level normal',
    'parts_used_1': 'Pump Oil',
    'qty_1': '0.5L',
    'supplier_bill_1': 'BILL001/15-09-2024',
    'value_1': '₹250',
    
    # Process 2: AIR CLEANER OIL CHECKUP
    'processed_date_2': '2024-09-15',
    'kilometer_reading_2': '17000',
    'action_processed_2': 'Cleaned and refilled',
    'observation_2': 'Filter cleaned thoroughly',
    'parts_used_2': 'Air Filter Oil',
    'qty_2': '0.3L',
    'supplier_bill_2': 'BILL002/15-09-2024',
    'value_2': '₹150',
    
    # Process 3: AIR CLEANER STAINER CHECKUP
    'processed_date_3': '2024-09-15',
    'kilometer_reading_3': '17000',
    'action_processed_3': 'Inspected and cleaned',
    'observation_3': 'Stainer in good condition',
    'parts_used_3': 'Cleaning agent',
    'qty_3': '1',
    'supplier_bill_3': 'BILL003/15-09-2024',
    'value_3': '₹100',
    
    # Process 4: JOINT TIE ROD & ENDS CHECKUP
    'processed_date_4': '2024-09-15',
    'kilometer_reading_4': '17000',
    'action_processed_4': 'Checked for wear and tear',
    'observation_4': 'All joints functioning properly',
    'parts_used_4': 'Grease',
    'qty_4': '0.2kg',
    'supplier_bill_4': 'BILL004/15-09-2024',
    'value_4': '₹200',
    
    # Process 5: UNLOAD KIT SERVICE
    'processed_date_5': '2024-09-15',
    'kilometer_reading_5': '17000',
    'action_processed_5': 'Complete servicing done',
    'observation_5': 'Kit working smoothly',
    'parts_used_5': 'Service kit parts',
    'qty_5': '1 set',
    'supplier_bill_5': 'BILL005/15-09-2024',
    'value_5': '₹500',
    
    # Process 6: VEHICLE START & ENGINE NOICE OBSERVATION
    'processed_date_6': '2024-09-15',
    'kilometer_reading_6': '17000',
    'action_processed_6': 'Tested engine start and listened for abnormal sounds',
    'observation_6': 'Engine starts smoothly, no unusual noise detected',
    'parts_used_6': 'None',
    'qty_6': '0',
    'supplier_bill_6': 'N/A',
    'value_6': '₹0'
}

print("Testing Half-Yearly Maintenance Save Function...")
print("=" * 60)

saved_count = save_halfyearly_maintenance(test_maintenance)

if saved_count > 0:
    print(f"\n✓ SUCCESS: Saved {saved_count} half-yearly maintenance record!")
    print(f"Vehicle ID: {test_maintenance['vehicle_id']}")
    print(f"Registration No: {test_maintenance['registration_no']}")
    print(f"Period: {test_maintenance['from_month']} to {test_maintenance['to_month']}")
    print(f"Processes completed: 6")
else:
    print("\n✗ FAILED: Could not save half-yearly maintenance record")
    print("Check the error messages above for details")

print("=" * 60)
