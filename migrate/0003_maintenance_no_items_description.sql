-- Migration: add no_items_description and utilized items metadata to maintenance_entry
-- Run this in your database (Supabase/Postgres) or apply via migration tool

ALTER TABLE IF EXISTS maintenance_entry
  ADD COLUMN IF NOT EXISTS no_items_description TEXT;

ALTER TABLE IF EXISTS maintenance_entry
  ADD COLUMN IF NOT EXISTS items_utilized BOOLEAN DEFAULT FALSE;

ALTER TABLE IF EXISTS maintenance_entry
  ADD COLUMN IF NOT EXISTS utilized_items JSONB;

-- Optionally set items_utilized = true when utilized_items is non-empty
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='maintenance_entry' AND column_name='utilized_items') THEN
    UPDATE maintenance_entry SET items_utilized = true WHERE utilized_items IS NOT NULL AND jsonb_array_length(utilized_items) > 0;
  END IF;
END
$$;

-- Helpful index for queries filtering by items_utilized
CREATE INDEX IF NOT EXISTS idx_maintenance_items_utilized ON maintenance_entry(items_utilized);
