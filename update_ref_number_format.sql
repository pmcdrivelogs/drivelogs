-- Update reference number format to include VOC- (Voucher)
-- Change from: PMC-ENGG-LOGI-0001 to PMC-ENGG-LOGI-VOC-0001
-- Change from: PMC-POLY-LOGI-0001 to PMC-POLY-LOGI-VOC-0001

-- Drop existing trigger and functions first (trigger must be dropped before functions it calls)
DROP TRIGGER IF EXISTS set_payment_ref_number ON payments;
DROP FUNCTION IF EXISTS set_payment_ref_number_func();
DROP FUNCTION IF EXISTS get_next_ref_number(text);

-- Create the main reference number generation function
CREATE OR REPLACE FUNCTION get_next_ref_number(p_institution_type text DEFAULT 'Engineering')
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    v_institution_code text;
    v_last_ref_number text;
    v_next_number integer;
    v_new_ref_number text;
BEGIN
    -- Determine institution code
    IF p_institution_type = 'Engineering' THEN
        v_institution_code := 'ENGG';
    ELSE
        v_institution_code := 'POLY';
    END IF;

    -- Get the last reference number for this institution type
    SELECT ref_number INTO v_last_ref_number
    FROM payments
    WHERE ref_number LIKE 'PMC-' || v_institution_code || '-LOGI-VOC-%'
    ORDER BY created_at DESC
    LIMIT 1;

    -- Extract the number from the last reference
    IF v_last_ref_number IS NOT NULL THEN
        -- Extract number after 'VOC-' (e.g., from 'PMC-ENGG-LOGI-VOC-0001' get '0001')
        v_next_number := CAST(SUBSTRING(v_last_ref_number FROM POSITION('VOC-' IN v_last_ref_number) + 4) AS INTEGER) + 1;
    ELSE
        -- First reference for this institution type
        v_next_number := 1;
    END IF;

    -- Generate the new reference number with VOC- prefix
    v_new_ref_number := 'PMC-' || v_institution_code || '-LOGI-VOC-' || LPAD(v_next_number::text, 4, '0');

    RETURN v_new_ref_number;
END;
$$;

-- Create the trigger function (must be created before the trigger)
CREATE OR REPLACE FUNCTION set_payment_ref_number_func()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.ref_number IS NULL AND NEW.payment_type = 'payment_voucher' THEN
        NEW.ref_number := get_next_ref_number(NEW.institution_type);
    END IF;
    RETURN NEW;
END;
$$;

-- Create trigger using the function (now the function exists)
CREATE TRIGGER set_payment_ref_number
BEFORE INSERT ON payments
FOR EACH ROW
WHEN (NEW.ref_number IS NULL AND NEW.payment_type = 'payment_voucher')
EXECUTE FUNCTION set_payment_ref_number_func();

-- Note: After running this SQL on Supabase:
-- 1. The get_next_ref_number function will generate references like PMC-ENGG-LOGI-VOC-0001
-- 2. The format includes "VOC-" to indicate it's a Voucher reference
-- 3. Make sure to update your Flask app to match this new format as fallback
