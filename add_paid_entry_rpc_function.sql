-- Migration: Add RPC functions for generating PAID entry numbers based on institution type
-- Format: PMC-{POLY|ENGG}-LOGI-PAID-{0001..9999}

-- Drop existing functions if they exist
DROP FUNCTION IF EXISTS get_next_paid_entry_no(TEXT);

-- Function to generate next PAID entry number based on institution type
CREATE OR REPLACE FUNCTION get_next_paid_entry_no(p_institution_type TEXT)
RETURNS TEXT AS $$
DECLARE
  v_prefix TEXT;
  v_last_num INT;
  v_new_num INT;
  v_full_entry TEXT;
  v_normalized_type TEXT;
BEGIN
  -- Normalize institution type to match check constraint values
  v_normalized_type := CASE 
    WHEN p_institution_type ILIKE '%poly%' THEN 'Polytechnic'
    ELSE 'Engineering'
  END;
  
  -- Determine prefix based on institution type
  IF v_normalized_type = 'Polytechnic' THEN
    v_prefix := 'PMC-POLY-LOGI-PAID';
  ELSE
    v_prefix := 'PMC-ENGG-LOGI-PAID';
  END IF;
  
  -- Find the highest existing number for this prefix
  SELECT COALESCE(
    MAX(CAST(SUBSTRING(entry_no FROM LENGTH(v_prefix) + 2) AS INT)), 
    0
  ) INTO v_last_num
  FROM payments
  WHERE entry_no LIKE v_prefix || '-%' 
    AND payment_type = 'payment_details'
    AND institution_type = v_normalized_type;
  
  -- Increment and format
  v_new_num := v_last_num + 1;
  v_full_entry := v_prefix || '-' || LPAD(CAST(v_new_num AS TEXT), 4, '0');
  
  RETURN v_full_entry;
END;
$$ LANGUAGE plpgsql;

-- Create comment for documentation
COMMENT ON FUNCTION get_next_paid_entry_no(TEXT) IS 'Generates next payment details entry number based on institution type (Polytechnic or Engineering)';
