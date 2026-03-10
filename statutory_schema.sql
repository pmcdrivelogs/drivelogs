-- Statutory Table Schema for Supabase
-- Run this in your Supabase SQL Editor

-- Drop existing table if exists (only use if you want to recreate)
-- DROP TABLE IF EXISTS statutory;

CREATE TABLE statutory (
  id SERIAL PRIMARY KEY,
  date DATE,
  time TEXT,
  entry_no TEXT,
  invoice_no TEXT,
  invoice_date DATE,
  statutory_body_id TEXT,
  type_of_transaction TEXT,
  validity_date DATE,
  rate NUMERIC(12, 2),
  taxable_amount NUMERIC(12, 2),
  sgst_percent NUMERIC(5, 2),
  sgst_amount NUMERIC(12, 2),
  cgst_percent NUMERIC(5, 2),
  cgst_amount NUMERIC(12, 2),
  igst_percent NUMERIC(5, 2),
  igst_amount NUMERIC(12, 2),
  total_amount NUMERIC(12, 2),
  entered_by TEXT,
  approved_by TEXT,
  approver_name TEXT,
  rejection_reason TEXT,
  user_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX idx_statutory_entry_no ON statutory(entry_no);
CREATE INDEX idx_statutory_date ON statutory(date);
CREATE INDEX idx_statutory_type ON statutory(type_of_transaction);

-- If you already have a statutory table and want to add the new columns, run this instead:
-- ALTER TABLE statutory 
--   ADD COLUMN IF NOT EXISTS taxable_amount NUMERIC(12, 2),
--   ADD COLUMN IF NOT EXISTS sgst_percent NUMERIC(5, 2),
--   ADD COLUMN IF NOT EXISTS sgst_amount NUMERIC(12, 2),
--   ADD COLUMN IF NOT EXISTS cgst_percent NUMERIC(5, 2),
--   ADD COLUMN IF NOT EXISTS cgst_amount NUMERIC(12, 2),
--   ADD COLUMN IF NOT EXISTS igst_percent NUMERIC(5, 2),
--   ADD COLUMN IF NOT EXISTS igst_amount NUMERIC(12, 2),
--   ADD COLUMN IF NOT EXISTS approver_name TEXT,
--   ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
--   DROP COLUMN IF EXISTS gst;
