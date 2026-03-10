-- Payment Management Table Schema
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_no VARCHAR(50) UNIQUE NOT NULL,
    ref_number VARCHAR(50) DEFAULT 'PMCTECH/LOGI/FORM 11/001',
    
    -- Payment Details
    date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    invoice_no VARCHAR(100),
    vendor_id VARCHAR(50),
    value DECIMAL(15, 2),
    dn VARCHAR(100),
    type_of_entry VARCHAR(100),
    mode_of_payment VARCHAR(100),
    payment_advice TEXT,
    payment_date DATE,
    amount DECIMAL(15, 2),
    
    -- Approval & Status
    approval_status VARCHAR(50) DEFAULT 'pending' CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    approved_by VARCHAR(255),
    approved_date TIMESTAMP,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entered_by VARCHAR(255),
    
    -- Metadata
    notes TEXT,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'cancelled'))
);

-- Function to auto-generate Payment Entry Number
CREATE OR REPLACE FUNCTION get_next_payment_entry_no()
RETURNS VARCHAR AS $$
DECLARE
    next_id INTEGER;
    new_entry_no VARCHAR(50);
BEGIN
    -- Get the highest existing entry number
    SELECT COALESCE(
        MAX(CAST(SUBSTRING(entry_no FROM 'PAY(\d+)') AS INTEGER)),
        0
    ) INTO next_id
    FROM payments
    WHERE entry_no ~ 'PAY\d+';
    
    -- Increment and format
    next_id := next_id + 1;
    new_entry_no := 'PMCTECH-LOGI-PAY' || LPAD(next_id::TEXT, 4, '0');
    
    RETURN new_entry_no;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-generate entry_no if not provided
CREATE OR REPLACE FUNCTION set_payment_entry_no()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.entry_no IS NULL OR NEW.entry_no = '' THEN
        NEW.entry_no := get_next_payment_entry_no();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_payment_entry_no
BEFORE INSERT ON payments
FOR EACH ROW
EXECUTE FUNCTION set_payment_entry_no();

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_payment_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_payment_timestamp
BEFORE UPDATE ON payments
FOR EACH ROW
EXECUTE FUNCTION update_payment_timestamp();

-- Create indexes for better performance
CREATE INDEX idx_payments_entry_no ON payments(entry_no);
CREATE INDEX idx_payments_vendor_id ON payments(vendor_id);
CREATE INDEX idx_payments_invoice_no ON payments(invoice_no);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_approval_status ON payments(approval_status);
CREATE INDEX idx_payments_payment_date ON payments(payment_date);
CREATE INDEX idx_payments_created_at ON payments(created_at);

-- Sample entry types
COMMENT ON COLUMN payments.type_of_entry IS 'Types: Advance Payment, Partial Payment, Full Payment, Refund, Adjustment, etc.';

-- Sample payment modes
COMMENT ON COLUMN payments.mode_of_payment IS 'Modes: Cash, Cheque, NEFT/RTGS, UPI, Online Transfer, Demand Draft, Credit Card, etc.';

-- Enable Row Level Security (optional)
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- Create policy for authenticated users
CREATE POLICY payments_policy ON payments
    FOR ALL
    USING (true)
    WITH CHECK (true);
