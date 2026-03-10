-- Migration: convert maintenance_entry.vehicle_id INTEGER -> VARCHAR(50)
-- Run this on your Postgres database (psql or Supabase SQL editor).
-- It will convert the column type and keep existing numeric values.

BEGIN;
ALTER TABLE maintenance_entry
  ALTER COLUMN vehicle_id TYPE VARCHAR(50)
  USING vehicle_id::text;
COMMIT;

-- After running this, new alphanumeric vehicle IDs (e.g. '96E') will be stored.
-- If you use a cached Supabase type mapping or a client that introspects types,
-- you may need to restart any running server/processes.
