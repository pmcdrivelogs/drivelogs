-- Add institution_type column to payments table for reference number generation
-- Purpose: Support different reference number formats for Engineering and Polytechnic institutions

ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS institution_type VARCHAR(50) DEFAULT 'Engineering' CHECK (institution_type IN ('Engineering', 'Polytechnic'));

COMMENT ON COLUMN payments.institution_type IS 'Institution type: Engineering or Polytechnic - used for generating appropriate reference numbers';

-- Drop old reference number function and create new one that uses institution_type
DROP FUNCTION IF EXISTS get_next_ref_number(p_institution_type VARCHAR) CASCADE;

CREATE OR REPLACE FUNCTION get_next_ref_number(p_institution_type VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
    next_id INTEGER;
    new_ref_number VARCHAR(50);
    institution_code VARCHAR(10);
BEGIN
    -- Determine institution code
    institution_code := CASE 
        WHEN p_institution_type = 'Engineering' THEN 'ENGG'
        WHEN p_institution_type = 'Polytechnic' THEN 'POLY'
        ELSE 'ENGG'  -- Default to Engineering
    END;
    
    -- Get the highest existing reference number for this institution type
    SELECT COALESCE(
        MAX(CAST(SUBSTRING(ref_number FROM 'LOGI-(\d+)') AS INTEGER)),
        0
    ) INTO next_id
    FROM payments
    WHERE ref_number LIKE 'PMC-' || institution_code || '-LOGI-%';
    
    -- Increment and format: PMC-ENGG-LOGI-0001 or PMC-POLY-LOGI-0001
    next_id := next_id + 1;
    new_ref_number := 'PMC-' || institution_code || '-LOGI-' || LPAD(next_id::TEXT, 4, '0');
    
    RETURN new_ref_number;
END;
$$ LANGUAGE plpgsql;

-- Function to set reference number if not provided
CREATE OR REPLACE FUNCTION set_payment_ref_number()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ref_number IS NULL OR NEW.ref_number = '' OR NEW.ref_number = 'PMCTECH/LOGI/FORM 11/001' THEN
        NEW.ref_number := get_next_ref_number(NEW.institution_type);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop old trigger and create new one
DROP TRIGGER IF EXISTS trigger_set_payment_ref_number ON payments;

CREATE TRIGGER trigger_set_payment_ref_number
BEFORE INSERT ON payments
FOR EACH ROW
EXECUTE FUNCTION set_payment_ref_number();
