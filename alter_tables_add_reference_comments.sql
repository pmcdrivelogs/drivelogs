-- SQL Script to add reference_number and comments columns to purchases, material_utilization, and scrap tables
-- Run this in Supabase SQL Editor

-- ALTER purchases table
ALTER TABLE purchases 
ADD COLUMN IF NOT EXISTS reference_number TEXT,
ADD COLUMN IF NOT EXISTS comments TEXT;

-- ALTER material_utilization table
ALTER TABLE material_utilization 
ADD COLUMN IF NOT EXISTS reference_number TEXT,
ADD COLUMN IF NOT EXISTS comments TEXT;

-- ALTER scrap table
ALTER TABLE scrap 
ADD COLUMN IF NOT EXISTS reference_number TEXT,
ADD COLUMN IF NOT EXISTS comments TEXT;

-- Verify the changes
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('purchases', 'material_utilization', 'scrap')
  AND column_name IN ('reference_number', 'comments')
ORDER BY table_name, column_name;
