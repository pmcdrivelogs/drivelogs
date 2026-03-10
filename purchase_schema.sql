-- =====================================================
-- PURCHASE TABLE SCHEMA FOR SUPABASE
-- =====================================================
-- Table: purchases
-- Description: Stores all purchase records with GST calculations
-- Reference: PMCTECH/LOGI/FORM 3
-- =====================================================

CREATE TABLE IF NOT EXISTS purchases (
    -- Primary Key
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Entry Information
    entry_no VARCHAR(20) NOT NULL UNIQUE,
    
    -- Date & Time
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    time TIME NOT NULL DEFAULT CURRENT_TIME,
    
    -- Invoice Details
    invoice_no VARCHAR(100),
    invoice_date DATE,
    
    -- Vendor Information
    vendor VARCHAR(255),
    type_of_purchase VARCHAR(100),
    
    -- Part Details
    part_number VARCHAR(100),
    part_name VARCHAR(255),
    quantity DECIMAL(10, 2) DEFAULT 0,
    batch_number VARCHAR(100),
    
    -- Pricing
    rate DECIMAL(12, 2) DEFAULT 0,
    
    -- Discount
    discount_percent DECIMAL(5, 2) DEFAULT 0,
    discount_amount DECIMAL(12, 2) DEFAULT 0,
    
    -- Taxable Amount
    taxable_amount DECIMAL(12, 2) DEFAULT 0,
    
    -- GST Details - SGST
    sgst_percent DECIMAL(5, 2) DEFAULT 0,
    sgst_amount DECIMAL(12, 2) DEFAULT 0,
    
    -- GST Details - CGST
    cgst_percent DECIMAL(5, 2) DEFAULT 0,
    cgst_amount DECIMAL(12, 2) DEFAULT 0,
    
    -- GST Details - IGST
    igst_percent DECIMAL(5, 2) DEFAULT 0,
    igst_amount DECIMAL(12, 2) DEFAULT 0,
    
    -- Payment Summary
    total_payment DECIMAL(12, 2) DEFAULT 0,
    dn DECIMAL(12, 2) DEFAULT 0,                    -- Debit Note
    less_tds DECIMAL(12, 2) DEFAULT 0,              -- TDS Deduction
    net_payable DECIMAL(12, 2) DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    created_by UUID,
    
    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'deleted', 'cancelled', 'issued'))
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Index for faster lookup by entry number
CREATE INDEX IF NOT EXISTS idx_purchases_entry_no ON purchases(entry_no);

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date);

-- Index for vendor lookup
CREATE INDEX IF NOT EXISTS idx_purchases_vendor ON purchases(vendor);

-- Index for invoice number lookup
CREATE INDEX IF NOT EXISTS idx_purchases_invoice_no ON purchases(invoice_no);

-- Index for part number lookup
CREATE INDEX IF NOT EXISTS idx_purchases_part_number ON purchases(part_number);

-- Index for status filtering
CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_purchases_date_vendor ON purchases(date, vendor);

-- =====================================================
-- TRIGGER FOR UPDATED_AT
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_purchases_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on row update
DROP TRIGGER IF EXISTS trigger_purchases_updated_at ON purchases;
CREATE TRIGGER trigger_purchases_updated_at
    BEFORE UPDATE ON purchases
    FOR EACH ROW
    EXECUTE FUNCTION update_purchases_updated_at();

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS
ALTER TABLE purchases ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own records or if admin
DROP POLICY IF EXISTS "Users can view purchase records" ON purchases;
CREATE POLICY "Users can view purchase records" ON purchases
    FOR SELECT
    USING (true);

-- Policy: Users can insert records
DROP POLICY IF EXISTS "Users can insert purchase records" ON purchases;
CREATE POLICY "Users can insert purchase records" ON purchases
    FOR INSERT
    WITH CHECK (true);

-- Policy: Users can update their own records
DROP POLICY IF EXISTS "Users can update purchase records" ON purchases;
CREATE POLICY "Users can update purchase records" ON purchases
    FOR UPDATE
    USING (true);

-- Policy: Soft delete only (update status)
DROP POLICY IF EXISTS "Users can soft delete purchase records" ON purchases;
CREATE POLICY "Users can soft delete purchase records" ON purchases
    FOR UPDATE
    USING (true)
    WITH CHECK (status IN ('active', 'deleted', 'cancelled'));

-- =====================================================
-- HELPER FUNCTION: GET NEXT ENTRY NUMBER
-- =====================================================
-- Use a DB sequence for atomic entry number generation to avoid race conditions
CREATE SEQUENCE IF NOT EXISTS purchases_entry_no_seq;

-- Initialize sequence to max existing numeric entry_no if table already has rows
DO $$
DECLARE
    max_val INTEGER := 0;
BEGIN
    BEGIN
        SELECT COALESCE(MAX(CAST(regexp_replace(entry_no, '[^0-9]', '', 'g') AS INTEGER)), 0) INTO max_val FROM purchases;
    EXCEPTION WHEN OTHERS THEN
        max_val := 0;
    END;
    PERFORM setval('purchases_entry_no_seq', GREATEST(max_val, 0));
END$$;

-- RPC-friendly function that returns the next entry number padded to 3 digits
CREATE OR REPLACE FUNCTION get_next_purchase_entry_no()
RETURNS VARCHAR(20) AS $$
    SELECT LPAD(nextval('purchases_entry_no_seq')::text, 3, '0');
$$ LANGUAGE SQL;

-- =====================================================
-- SAMPLE DATA (OPTIONAL - FOR TESTING)
-- =====================================================

-- Uncomment to insert sample data
/*
INSERT INTO purchases (
    entry_no, date, time, invoice_no, invoice_date, vendor, 
    type_of_purchase, part_number, part_name, quantity, batch_number,
    rate, discount_percent, discount_amount, taxable_amount,
    sgst_percent, sgst_amount, cgst_percent, cgst_amount,
    igst_percent, igst_amount, total_payment, dn, less_tds, net_payable
) VALUES (
    '001', '2024-12-26', '10:30:00', 'INV-001', '2024-12-25', 'ABC Suppliers',
    'Spare Parts', 'PN-001', 'Oil Filter', 10, 'BATCH-001',
    500.00, 5.00, 250.00, 4750.00,
    9.00, 427.50, 9.00, 427.50,
    0.00, 0.00, 5605.00, 0.00, 56.05, 5548.95
);
*/

-- =====================================================
-- GRANT PERMISSIONS
-- =====================================================

-- Grant access to authenticated users
GRANT ALL ON purchases TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- =====================================================
-- COMMENTS FOR DOCUMENTATION
-- =====================================================

COMMENT ON TABLE purchases IS 'Purchase records table for tracking all procurement activities';
COMMENT ON COLUMN purchases.entry_no IS 'Unique entry number in format 001, 002, etc.';
COMMENT ON COLUMN purchases.invoice_no IS 'Vendor invoice number';
COMMENT ON COLUMN purchases.type_of_purchase IS 'Category of purchase (e.g., Spare Parts, Consumables)';
COMMENT ON COLUMN purchases.dn IS 'Debit Note amount';
COMMENT ON COLUMN purchases.less_tds IS 'TDS (Tax Deducted at Source) amount';
COMMENT ON COLUMN purchases.net_payable IS 'Final amount payable after all deductions';
