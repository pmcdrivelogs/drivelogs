-- ============================================================================
-- PAYMENT VOUCHER SCHEMA UPDATES
-- ============================================================================
-- Purpose: Alter existing payments table and create new voucher line items table
-- Date: February 10, 2026
-- Reference: PMCTECH/LOGI/FORM 11/VOUCHER
-- ============================================================================

-- Step 1: Alter payments table to add voucher-specific columns
-- ============================================================================

ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS total_parts DECIMAL(15, 2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS total_labour DECIMAL(15, 2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS total_taxable DECIMAL(15, 2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS total_gst DECIMAL(15, 2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS total_dn DECIMAL(15, 2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS total_payable DECIMAL(15, 2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS payment_type VARCHAR(50) DEFAULT 'payment_details' CHECK (payment_type IN ('payment_voucher', 'payment_details'));

-- Add comments for new columns
COMMENT ON COLUMN payments.total_parts IS 'Total parts price from all line items (for payment vouchers)';
COMMENT ON COLUMN payments.total_labour IS 'Total labour charges from all line items (for payment vouchers)';
COMMENT ON COLUMN payments.total_taxable IS 'Total taxable amount (Parts + Labour) from all line items';
COMMENT ON COLUMN payments.total_gst IS 'Total GST amount from all line items';
COMMENT ON COLUMN payments.total_dn IS 'Total Debit Note (DN) amount from all line items';
COMMENT ON COLUMN payments.total_payable IS 'Total payable amount (Taxable + GST - DN) from all line items';
COMMENT ON COLUMN payments.payment_type IS 'Type of payment entry: payment_voucher or payment_details';


-- Step 2: Create payment_voucher_items table for line items
-- ============================================================================

CREATE TABLE IF NOT EXISTS payment_voucher_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Key Reference
    payment_entry_no VARCHAR(50) NOT NULL,
    
    -- Line Item Details
    line_number INTEGER NOT NULL,
    bus_reg_no VARCHAR(50),
    invoice_no VARCHAR(100),
    work_description TEXT NOT NULL,
    
    -- Financial Breakdown
    parts_price DECIMAL(12, 2) DEFAULT 0.00,
    labour_charge DECIMAL(12, 2) DEFAULT 0.00,
    taxable_amount DECIMAL(12, 2) DEFAULT 0.00,
    gst_amount DECIMAL(12, 2) DEFAULT 0.00,
    dn_amount DECIMAL(12, 2) DEFAULT 0.00,
    payable_amount DECIMAL(12, 2) DEFAULT 0.00,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key Constraint
    CONSTRAINT fk_payment_entry 
        FOREIGN KEY (payment_entry_no) 
        REFERENCES payments(entry_no) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    
    -- Unique constraint to prevent duplicate line numbers per payment
    CONSTRAINT unique_line_per_payment 
        UNIQUE (payment_entry_no, line_number)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_voucher_items_payment_entry ON payment_voucher_items(payment_entry_no);
CREATE INDEX IF NOT EXISTS idx_voucher_items_invoice ON payment_voucher_items(invoice_no);
CREATE INDEX IF NOT EXISTS idx_voucher_items_bus_reg ON payment_voucher_items(bus_reg_no);
CREATE INDEX IF NOT EXISTS idx_voucher_items_line_number ON payment_voucher_items(line_number);

-- Add trigger to update timestamp
CREATE OR REPLACE FUNCTION update_voucher_item_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_voucher_item_timestamp ON payment_voucher_items;

CREATE TRIGGER trigger_update_voucher_item_timestamp
BEFORE UPDATE ON payment_voucher_items
FOR EACH ROW
EXECUTE FUNCTION update_voucher_item_timestamp();

-- Comments on table and columns
COMMENT ON TABLE payment_voucher_items IS 'Stores line items for payment vouchers with detailed breakdown of parts, labour, GST, and DN';
COMMENT ON COLUMN payment_voucher_items.payment_entry_no IS 'References the parent payment entry number from payments table';
COMMENT ON COLUMN payment_voucher_items.line_number IS 'Sequential line number within the voucher (1, 2, 3, etc.)';
COMMENT ON COLUMN payment_voucher_items.bus_reg_no IS 'Bus registration number for which the payment is made';
COMMENT ON COLUMN payment_voucher_items.work_description IS 'Description of part or work performed';
COMMENT ON COLUMN payment_voucher_items.parts_price IS 'Cost of parts for this line item';
COMMENT ON COLUMN payment_voucher_items.labour_charge IS 'Labour charges for this line item';
COMMENT ON COLUMN payment_voucher_items.taxable_amount IS 'Taxable amount (Parts + Labour) - auto-calculated';
COMMENT ON COLUMN payment_voucher_items.gst_amount IS 'GST amount applied to this line item';
COMMENT ON COLUMN payment_voucher_items.dn_amount IS 'Debit Note amount to be deducted from this line item';
COMMENT ON COLUMN payment_voucher_items.payable_amount IS 'Final payable amount (Taxable + GST - DN) - auto-calculated';


-- Step 3: Create view for complete voucher details
-- ============================================================================

CREATE OR REPLACE VIEW v_payment_voucher_complete AS
SELECT 
    p.id,
    p.entry_no,
    p.ref_number,
    p.date_time,
    p.invoice_no,
    p.vendor_id,
    p.payment_type,
    p.total_parts,
    p.total_labour,
    p.total_taxable,
    p.total_gst,
    p.total_dn,
    p.total_payable,
    p.approval_status,
    p.approved_by,
    p.approved_date,
    p.created_at,
    p.entered_by,
    p.notes,
    p.status,
    
    -- Aggregated line item data
    COUNT(vi.id) as item_count,
    json_agg(
        json_build_object(
            'line_number', vi.line_number,
            'bus_reg_no', vi.bus_reg_no,
            'invoice_no', vi.invoice_no,
            'work_description', vi.work_description,
            'parts_price', vi.parts_price,
            'labour_charge', vi.labour_charge,
            'taxable_amount', vi.taxable_amount,
            'gst_amount', vi.gst_amount,
            'dn_amount', vi.dn_amount,
            'payable_amount', vi.payable_amount
        ) ORDER BY vi.line_number
    ) as line_items
    
FROM payments p
LEFT JOIN payment_voucher_items vi ON p.entry_no = vi.payment_entry_no
WHERE p.payment_type = 'payment_voucher'
GROUP BY 
    p.id, p.entry_no, p.ref_number, p.date_time, p.invoice_no, p.vendor_id,
    p.payment_type, p.total_parts, p.total_labour, p.total_taxable, 
    p.total_gst, p.total_dn, p.total_payable, p.approval_status, 
    p.approved_by, p.approved_date, p.created_at, p.entered_by, p.notes, p.status;

COMMENT ON VIEW v_payment_voucher_complete IS 'Complete view of payment vouchers with all line items aggregated as JSON';


-- Step 4: Create helper function to insert voucher with line items
-- ============================================================================

CREATE OR REPLACE FUNCTION insert_payment_voucher(
    p_invoice_no VARCHAR(100),
    p_entered_by VARCHAR(255),
    p_total_parts DECIMAL(15, 2),
    p_total_labour DECIMAL(15, 2),
    p_total_taxable DECIMAL(15, 2),
    p_total_gst DECIMAL(15, 2),
    p_total_dn DECIMAL(15, 2),
    p_total_payable DECIMAL(15, 2),
    p_line_items JSONB
)
RETURNS VARCHAR AS $$
DECLARE
    v_entry_no VARCHAR(50);
    v_line_item JSONB;
    v_line_number INTEGER := 0;
BEGIN
    -- Insert main payment record
    INSERT INTO payments (
        invoice_no,
        entered_by,
        payment_type,
        total_parts,
        total_labour,
        total_taxable,
        total_gst,
        total_dn,
        total_payable,
        approval_status,
        status
    ) VALUES (
        p_invoice_no,
        p_entered_by,
        'payment_voucher',
        p_total_parts,
        p_total_labour,
        p_total_taxable,
        p_total_gst,
        p_total_dn,
        p_total_payable,
        'pending',
        'active'
    ) RETURNING entry_no INTO v_entry_no;
    
    -- Insert line items
    FOR v_line_item IN SELECT * FROM jsonb_array_elements(p_line_items)
    LOOP
        v_line_number := v_line_number + 1;
        
        INSERT INTO payment_voucher_items (
            payment_entry_no,
            line_number,
            bus_reg_no,
            invoice_no,
            work_description,
            parts_price,
            labour_charge,
            taxable_amount,
            gst_amount,
            dn_amount,
            payable_amount
        ) VALUES (
            v_entry_no,
            v_line_number,
            (v_line_item->>'bus_reg_no')::VARCHAR,
            (v_line_item->>'invoice_no')::VARCHAR,
            (v_line_item->>'work_description')::TEXT,
            COALESCE((v_line_item->>'parts_price')::DECIMAL, 0),
            COALESCE((v_line_item->>'labour_charge')::DECIMAL, 0),
            COALESCE((v_line_item->>'taxable_amount')::DECIMAL, 0),
            COALESCE((v_line_item->>'gst_amount')::DECIMAL, 0),
            COALESCE((v_line_item->>'dn_amount')::DECIMAL, 0),
            COALESCE((v_line_item->>'payable_amount')::DECIMAL, 0)
        );
    END LOOP;
    
    RETURN v_entry_no;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION insert_payment_voucher IS 'Inserts a payment voucher with multiple line items in a single transaction';


-- Step 5: Create helper function to calculate voucher totals
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_voucher_totals(p_entry_no VARCHAR(50))
RETURNS TABLE (
    total_parts DECIMAL(15, 2),
    total_labour DECIMAL(15, 2),
    total_taxable DECIMAL(15, 2),
    total_gst DECIMAL(15, 2),
    total_dn DECIMAL(15, 2),
    total_payable DECIMAL(15, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(SUM(parts_price), 0)::DECIMAL(15, 2),
        COALESCE(SUM(labour_charge), 0)::DECIMAL(15, 2),
        COALESCE(SUM(taxable_amount), 0)::DECIMAL(15, 2),
        COALESCE(SUM(gst_amount), 0)::DECIMAL(15, 2),
        COALESCE(SUM(dn_amount), 0)::DECIMAL(15, 2),
        COALESCE(SUM(payable_amount), 0)::DECIMAL(15, 2)
    FROM payment_voucher_items
    WHERE payment_entry_no = p_entry_no;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_voucher_totals IS 'Calculates total amounts for a payment voucher from its line items';


-- Step 6: Sample query examples
-- ============================================================================

-- Example 1: Get all payment vouchers with their line items
-- SELECT * FROM v_payment_voucher_complete WHERE status = 'active';

-- Example 2: Get specific voucher details
-- SELECT * FROM payments WHERE entry_no = 'PMCTECH-LOGI-PAY0001' AND payment_type = 'payment_voucher';
-- SELECT * FROM payment_voucher_items WHERE payment_entry_no = 'PMCTECH-LOGI-PAY0001' ORDER BY line_number;

-- Example 3: Get voucher summary statistics
-- SELECT 
--     COUNT(*) as total_vouchers,
--     SUM(total_payable) as total_amount,
--     approval_status
-- FROM payments 
-- WHERE payment_type = 'payment_voucher'
-- GROUP BY approval_status;

-- Example 4: Get vouchers by vendor (via invoice)
-- SELECT p.*, v.vendor_name 
-- FROM payments p
-- JOIN purchases pu ON p.invoice_no = pu.invoice_no
-- JOIN vendors v ON pu.vendor_id = v.vendor_id
-- WHERE p.payment_type = 'payment_voucher';


-- ============================================================================
-- END OF SCHEMA UPDATE
-- ============================================================================
