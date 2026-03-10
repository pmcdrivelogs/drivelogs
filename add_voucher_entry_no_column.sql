-- Migration: Add voucher_entry_no column to payments table
-- This column links payment_details records to payment_voucher records

-- Add the column to track which voucher this payment belongs to
ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS voucher_entry_no VARCHAR(50);

-- Create an index for faster lookups
CREATE INDEX IF NOT EXISTS idx_payments_voucher_entry_no 
ON payments(voucher_entry_no);

-- Add a comment explaining the column
COMMENT ON COLUMN payments.voucher_entry_no IS 'Links payment_details records to payment_voucher records via entry_no';
