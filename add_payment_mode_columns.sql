-- Migration: Add payment method specific columns to payments table
-- These columns store transaction/reference numbers for different payment modes

ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS cheque_number VARCHAR(100),
ADD COLUMN IF NOT EXISTS utr_number VARCHAR(100),
ADD COLUMN IF NOT EXISTS neft_rtgs_number VARCHAR(100),
ADD COLUMN IF NOT EXISTS draft_number VARCHAR(100),
ADD COLUMN IF NOT EXISTS card_number VARCHAR(100);

-- Add comments for documentation
COMMENT ON COLUMN payments.cheque_number IS 'Cheque number for Cheque mode payments';
COMMENT ON COLUMN payments.utr_number IS 'UTR (Unique Transaction Reference) number for UPI mode payments';
COMMENT ON COLUMN payments.neft_rtgs_number IS 'NEFT/RTGS transaction reference number';
COMMENT ON COLUMN payments.draft_number IS 'Demand Draft number';
COMMENT ON COLUMN payments.card_number IS 'Credit Card reference/transaction number (masked for security)';
