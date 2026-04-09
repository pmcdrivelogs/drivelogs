-- ============================================================
-- ALTER TABLE: daily_technical_remarks
-- ============================================================
-- 1. Change `amount` column from TEXT to NUMERIC so arithmetic
--    queries and sorting work correctly.
-- 2. Add a composite index on (vehicle_id, date) to speed up
--    the "fetch by vehicle + date" API used in the maintenance form.
-- ============================================================

-- Step 1: Convert existing text amounts to NUMERIC.
--   USING clause safely casts values; NULLs / empty strings become NULL.
ALTER TABLE public.daily_technical_remarks
  ALTER COLUMN amount TYPE NUMERIC(12, 2)
    USING CASE
      WHEN amount IS NULL OR TRIM(amount::TEXT) = '' THEN NULL
      ELSE amount::TEXT::NUMERIC(12, 2)
    END;

-- Step 2: Add composite index on vehicle_id + date for fast lookup
--   (used by /api/daily-technical-remarks/by-vehicle-date).
CREATE INDEX IF NOT EXISTS idx_dtr_vehicle_date
  ON public.daily_technical_remarks (vehicle_id, date);

-- Step 3 (optional): Add updated_at trigger to keep it in sync.
--   Skip if you already have one.
-- CREATE OR REPLACE FUNCTION set_updated_at()
-- RETURNS TRIGGER AS $$
-- BEGIN
--   NEW.updated_at = CURRENT_TIMESTAMP;
--   RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;
--
-- CREATE OR REPLACE TRIGGER trg_dtr_updated_at
--   BEFORE UPDATE ON public.daily_technical_remarks
--   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
