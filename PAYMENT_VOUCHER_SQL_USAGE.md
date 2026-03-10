# Payment Voucher SQL Schema Documentation

## 📋 Overview
This document explains the database schema changes for the Payment Voucher system.

---

## 🗂️ Files

1. **`alter_payment_voucher_schema.sql`** - Main schema update script
2. **`rollback_payment_voucher_schema.sql`** - Rollback script (in case of issues)

---

## 📊 Database Changes

### 1. **Altered Table: `payments`**

New columns added:

| Column | Type | Description |
|--------|------|-------------|
| `total_parts` | DECIMAL(15,2) | Sum of all parts prices |
| `total_labour` | DECIMAL(15,2) | Sum of all labour charges |
| `total_taxable` | DECIMAL(15,2) | Total taxable amount (Parts + Labour) |
| `total_gst` | DECIMAL(15,2) | Total GST amount |
| `total_dn` | DECIMAL(15,2) | Total Debit Note deductions |
| `total_payable` | DECIMAL(15,2) | Final payable amount |
| `payment_type` | VARCHAR(50) | Either 'payment_voucher' or 'payment_details' |

---

### 2. **New Table: `payment_voucher_items`**

Stores line items for each payment voucher.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `payment_entry_no` | VARCHAR(50) | Foreign key to `payments.entry_no` |
| `line_number` | INTEGER | Sequential line number (1, 2, 3...) |
| `bus_reg_no` | VARCHAR(50) | Bus registration number |
| `invoice_no` | VARCHAR(100) | Invoice number |
| `work_description` | TEXT | Part or work description |
| `parts_price` | DECIMAL(12,2) | Parts cost |
| `labour_charge` | DECIMAL(12,2) | Labour cost |
| `taxable_amount` | DECIMAL(12,2) | Taxable amount (calculated) |
| `gst_amount` | DECIMAL(12,2) | GST amount |
| `dn_amount` | DECIMAL(12,2) | Debit note amount |
| `payable_amount` | DECIMAL(12,2) | Final payable (calculated) |

**Relationships:**
- Foreign key to `payments(entry_no)` with CASCADE delete/update
- Unique constraint on `(payment_entry_no, line_number)`

---

### 3. **New View: `v_payment_voucher_complete`**

Combines payment header with line items as JSON.

```sql
SELECT * FROM v_payment_voucher_complete 
WHERE entry_no = 'PMCTECH-LOGI-PAY0001';
```

Returns the payment record with an aggregated `line_items` JSON array.

---

## 🔧 Helper Functions

### 1. `insert_payment_voucher()`

Inserts a payment voucher with multiple line items in a single transaction.

**Parameters:**
- `p_invoice_no` - Invoice number
- `p_entered_by` - User who entered the record
- `p_total_parts` - Total parts amount
- `p_total_labour` - Total labour amount
- `p_total_taxable` - Total taxable amount
- `p_total_gst` - Total GST amount
- `p_total_dn` - Total DN amount
- `p_total_payable` - Total payable amount
- `p_line_items` - JSONB array of line items

**Example Usage:**
```sql
SELECT insert_payment_voucher(
    'INV-2024-001',
    'admin@pmctech.edu',
    5000.00,
    2000.00,
    7000.00,
    1260.00,
    500.00,
    7760.00,
    '[
        {
            "bus_reg_no": "TN01AB1234",
            "invoice_no": "INV-2024-001",
            "work_description": "Engine repair",
            "parts_price": 3000,
            "labour_charge": 1000,
            "taxable_amount": 4000,
            "gst_amount": 720,
            "dn_amount": 200,
            "payable_amount": 4520
        },
        {
            "bus_reg_no": "TN01AB5678",
            "invoice_no": "INV-2024-001",
            "work_description": "Brake pad replacement",
            "parts_price": 2000,
            "labour_charge": 1000,
            "taxable_amount": 3000,
            "gst_amount": 540,
            "dn_amount": 300,
            "payable_amount": 3240
        }
    ]'::JSONB
);
```

---

### 2. `calculate_voucher_totals()`

Recalculates totals for a voucher from its line items.

**Example:**
```sql
SELECT * FROM calculate_voucher_totals('PMCTECH-LOGI-PAY0001');
```

---

## 🚀 Installation Steps

### Step 1: Backup Database
```sql
-- Create backup
pg_dump -U your_username -d your_database > backup_before_voucher_schema.sql
```

### Step 2: Run Schema Update
```bash
# Using psql
psql -U your_username -d your_database -f alter_payment_voucher_schema.sql

# Or in Supabase SQL Editor, copy and paste the entire file
```

### Step 3: Verify Installation
```sql
-- Check if new columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'payments' 
AND column_name IN ('total_parts', 'total_labour', 'payment_type');

-- Check if new table exists
SELECT COUNT(*) FROM payment_voucher_items;

-- Check if view exists
SELECT COUNT(*) FROM v_payment_voucher_complete;
```

---

## 📝 Common Queries

### Get all payment vouchers with line items
```sql
SELECT * FROM v_payment_voucher_complete 
WHERE status = 'active'
ORDER BY created_at DESC;
```

### Get specific voucher details
```sql
-- Header
SELECT * FROM payments 
WHERE entry_no = 'PMCTECH-LOGI-PAY0001';

-- Line items
SELECT * FROM payment_voucher_items 
WHERE payment_entry_no = 'PMCTECH-LOGI-PAY0001' 
ORDER BY line_number;
```

### Get vouchers for a specific invoice
```sql
SELECT p.*, 
       COUNT(vi.id) as item_count,
       p.total_payable
FROM payments p
LEFT JOIN payment_voucher_items vi ON p.entry_no = vi.payment_entry_no
WHERE p.invoice_no = 'INV-2024-001' 
  AND p.payment_type = 'payment_voucher'
GROUP BY p.entry_no;
```

### Get pending vouchers for approval
```sql
SELECT entry_no, invoice_no, total_payable, created_at
FROM payments
WHERE payment_type = 'payment_voucher'
  AND approval_status = 'pending'
ORDER BY created_at DESC;
```

### Get voucher statistics
```sql
SELECT 
    approval_status,
    COUNT(*) as total_vouchers,
    SUM(total_payable) as total_amount
FROM payments 
WHERE payment_type = 'payment_voucher'
GROUP BY approval_status;
```

### Search vouchers by bus registration number
```sql
SELECT DISTINCT p.*
FROM payments p
JOIN payment_voucher_items vi ON p.entry_no = vi.payment_entry_no
WHERE vi.bus_reg_no LIKE '%TN01AB%'
  AND p.payment_type = 'payment_voucher';
```

---

## 🔄 Data Migration (if needed)

If you have existing payment records that should be vouchers:

```sql
-- Example: Convert existing payments to vouchers
UPDATE payments 
SET payment_type = 'payment_voucher'
WHERE invoice_no IN ('INV-001', 'INV-002');

-- Note: You'll need to manually create line items for these
```

---

## ⚠️ Important Notes

1. **Foreign Key**: Line items are CASCADE deleted when parent payment is deleted
2. **Transaction Safety**: All inserts should be wrapped in transactions
3. **Validation**: Frontend should validate that totals match before submission
4. **Performance**: Indexes are created on frequently queried columns
5. **Backup**: Always backup before running schema changes

---

## 🔙 Rollback Procedure

If you need to undo the changes:

```bash
# Run the rollback script
psql -U your_username -d your_database -f rollback_payment_voucher_schema.sql

# Restore from backup if needed
psql -U your_username -d your_database < backup_before_voucher_schema.sql
```

---

## 🐛 Troubleshooting

### Issue: Foreign key constraint error
**Solution:** Ensure parent payment record exists before inserting line items

### Issue: Duplicate line number error
**Solution:** Line numbers must be unique per payment_entry_no

### Issue: Column already exists error
**Solution:** Safe to ignore - script uses `IF NOT EXISTS` checks

---

## 📞 Support

For issues or questions, contact your database administrator or refer to:
- Supabase Documentation: https://supabase.com/docs
- PostgreSQL Documentation: https://www.postgresql.org/docs/

---

**Last Updated:** February 10, 2026  
**Version:** 1.0  
**Reference:** PMCTECH/LOGI/FORM 11/VOUCHER
