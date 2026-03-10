# Stock Inventory System Integration Flow

## Overview
The Material Utilization module is fully integrated with the Purchases and Stock Inventory system. Parts can only be utilized if they have been purchased and are available in stock.

## Data Flow

```
PURCHASES TABLE
    ↓ (Parts purchased)
    ├─→ STOCK ISSUE REGISTER (Parts issued to departments)
    └─→ MATERIAL UTILIZATION (Parts used for vehicle maintenance)
```

## Available Quantity Calculation

**Formula:**
```
Available Quantity = Total Purchased - Total Issued - Total Utilized
```

**SQL Implementation:**
```sql
SELECT 
    p.part_no,
    p.part_name,
    SUM(p.quantity) - 
    COALESCE((SELECT SUM(quantity_issued) FROM stock_issue_register WHERE part_no = p.part_no), 0) -
    COALESCE((SELECT SUM(quantity) FROM material_utilization WHERE part_no = p.part_no), 0) 
    as available_quantity
FROM purchases p
WHERE p.status = 'active'
GROUP BY p.part_no, p.part_name
HAVING available_quantity > 0
```

## Form Features

### Material Utilization Form (FORM 10/001)

1. **Part Selection Dropdown**
   - Shows only parts from `purchases` table with `status = 'active'`
   - Displays: `Part No - Part Name (Available: X)`
   - Auto-fills Part Name when selected

2. **Quantity Validation**
   - Warns if requested quantity exceeds available stock
   - Warning message: "⚠️ Quantity exceeds available stock!"
   - Still allows submission (for special cases)

3. **Vehicle Integration**
   - Dropdown populated from `vehicles` table
   - Auto-fills registration number

4. **Approval Workflow**
   - YES/NO toggle buttons
   - Required field before submission
   - Stored in database for audit trail

## Database Tables

### 1. purchases
```sql
- part_no VARCHAR(100)
- part_name VARCHAR(255)
- quantity DECIMAL(10,2)
- status VARCHAR(20) CHECK ('active', 'deleted', 'cancelled', 'issued')
```

### 2. stock_issue_register
```sql
- part_no VARCHAR(100)
- quantity_issued DECIMAL(10,2)
- issued_to VARCHAR(255)
```

### 3. material_utilization
```sql
- part_no VARCHAR(100)
- part_name VARCHAR(255)
- quantity DECIMAL(10,2)
- vehicle_id VARCHAR(50)
- approved VARCHAR(10) CHECK ('YES', 'NO')
```

## Backend Implementation

### `/utilization` Route (app.py)

**GET Request:**
- Fetches next entry number via `get_next_material_utilization_entry_no()`
- Loads vehicles from `vehicles` table
- Calculates available quantity for each part from `purchases` table
- Only shows parts with `available_quantity > 0`

**POST Request:**
- Validates form data
- Saves to `material_utilization` table
- Decreases available stock automatically (via calculation)

## User Workflow

1. **Purchase Materials** → Add to `purchases` table
2. **Issue Stock** (Optional) → Record in `stock_issue_register`
3. **Utilize Materials** → Select from available parts in utilization form
4. **Stock Updates** → Available quantity auto-calculated

## Key Benefits

✅ **Data Integrity:** Can't utilize non-existent parts
✅ **Stock Tracking:** Real-time available quantity
✅ **Audit Trail:** All transactions recorded
✅ **User-Friendly:** Auto-fill and validation
✅ **Warning System:** Alerts on low/exceeded stock

## Files Modified

1. `material_utilization.html` - Part dropdown with available quantity
2. `material_utilization_schema.sql` - Updated comments
3. `app.py` - Added parts query with availability calculation

## Testing Checklist

- [ ] Purchase parts appear in utilization dropdown
- [ ] Available quantity calculates correctly
- [ ] Warning shows when quantity exceeds stock
- [ ] Part name auto-fills when selected
- [ ] Form validates approval selection
- [ ] Database saves correctly
- [ ] Entry number auto-generates
