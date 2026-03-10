"""Test script for weekly attention checklist"""
from database import save_weekly_attention

# Test data - 2 sets of all 20 processes
processes = [
    "FLOOR BROOMING",
    "COMPLETE WATER WASHING",
    "TIRONS END GREASING",
    "TYRE INFLATION PHYSICAL EXAM",
    "ENGINE OIL CHECKUP & TOPUP",
    "ANY OTHER OIL SPILLLE CHECKUP",
    "FAN BELTS TENSION CHECKUP",
    "RADIATOR HOSES",
    "FUEL HOSES",
    "BREAK LINING CHECKUP & ADJUSTMENT",
    "CLUTCH FLY & OIL CHECK & ADJUSTMENT",
    "UNDER CHASIS BOLTS CHECK UP",
    "JOINT BOLTS CHECKUP & GREASING",
    "SPRING PLSTS CONDITION CHECKUP",
    "DRINING WATER FROM VACCUM TANK",
    "WIPER CONDITION CHECKUP",
    "FIRE EXTINGUISHER LEVEL",
    "STARTER & ALTERNATOR CHECKUP",
    "BATTERY WATER LEVEL & CONDITION",
    "SEATS CONDITION, SCREWS & BOLTS"
]

# Create test entries for Set 1 (Vehicle V001)
test_entries_set1 = []
for process in processes:
    entry = {
        'vehicle_id': 'V001',
        'registration_no': 'TN01AB1234',
        'process_name': process,
        'week1_date': '2024-01-01',
        'week1_km': '15000',
        'week1_obs': 'Good condition',
        'week2_date': '2024-01-08',
        'week2_km': '15500',
        'week2_obs': 'Checked and OK'
    }
    test_entries_set1.append(entry)

# Create test entries for Set 2 (Vehicle V002)
test_entries_set2 = []
for process in processes:
    entry = {
        'vehicle_id': 'V002',
        'registration_no': 'TN02CD5678',
        'process_name': process,
        'week1_date': '2024-01-02',
        'week1_km': '20000',
        'week1_obs': 'Needs attention',
        'week2_date': '2024-01-09',
        'week2_km': '20600',
        'week2_obs': 'Fixed and verified'
    }
    test_entries_set2.append(entry)

# Combine both sets
all_entries = test_entries_set1 + test_entries_set2

# Test the save function
print("Testing save_weekly_attention...")
print(f"Attempting to save {len(all_entries)} weekly attention records...")

result = save_weekly_attention(all_entries)

print(f"\n{'='*60}")
if result == len(all_entries):
    print(f"✓ SUCCESS: Saved {result} weekly attention record(s)")
    print(f"  - Vehicle V001: {len(test_entries_set1)} processes")
    print(f"  - Vehicle V002: {len(test_entries_set2)} processes")
else:
    print(f"✗ PARTIAL: Saved {result} out of {len(all_entries)} records")
print(f"{'='*60}\n")
