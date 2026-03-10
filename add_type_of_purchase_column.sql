-- Migration: add_type_of_purchase_column.sql
-- Purpose: Add legacy `type_of_purchase` column to `vendors` table
-- This is idempotent and safe to run multiple times.

-- Adds a TEXT column `type_of_purchase` if it does not exist.
ALTER TABLE vendors
  ADD COLUMN IF NOT EXISTS type_of_purchase TEXT;

-- Optionally you may want to populate this column from the
-- normalized `vendor_purchase_types` table (if you migrated earlier).
-- Example to aggregate existing normalized rows into the legacy column:
-- UPDATE vendors v
-- SET type_of_purchase = sub.types
-- FROM (
--   SELECT vendor_id, string_agg(purchase_type, ', ') AS types
--   FROM vendor_purchase_types
--   GROUP BY vendor_id
-- ) AS sub
-- WHERE v.vendor_id = sub.vendor_id;

-- After running this migration on Supabase, refresh the API schema cache in
-- the Supabase dashboard (API → click "Refresh" or reopen the SQL editor).
-- If you're using a self-hosted PostgREST, restart the PostgREST service.

-- NOTE: This file only restores the column for backward compatibility.
-- Recommended long-term approach is to use a normalized table
-- `vendor_purchase_types` and update application code to read/write from it.
