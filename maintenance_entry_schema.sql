-- Schema for `maintenance_entry` matching the Maintenance Entry form
-- Fields reflect the inputs in templates/maintenance_image.html
CREATE TABLE IF NOT EXISTS maintenance_entry (
  id SERIAL PRIMARY KEY,
  entry_no VARCHAR(48) UNIQUE,
  date_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  vehicle_id VARCHAR(50),
  registration_no VARCHAR(32),
  driver_incharge VARCHAR(128),
  drivers_voice TEXT,
  technician_alloted VARCHAR(128),
  
  technician_observation TEXT,
  possible_ways TEXT,
  parts_required TEXT,
  processed_by VARCHAR(128),
  approved BOOLEAN DEFAULT FALSE,
  created_by VARCHAR(128),
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
  updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

-- Workflow fields: status and estimated_date
-- Add these columns to support the job-card lifecycle (new -> pending -> corrected)
-- Included in CREATE so new installs have the columns.
ALTER TABLE IF EXISTS maintenance_entry
  ADD COLUMN IF NOT EXISTS status VARCHAR(24) DEFAULT 'new' NOT NULL;

ALTER TABLE IF EXISTS maintenance_entry
  ADD COLUMN IF NOT EXISTS estimated_date TIMESTAMP WITHOUT TIME ZONE;

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_maintenance_vehicle_id ON maintenance_entry(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_registration_no ON maintenance_entry(registration_no);
CREATE INDEX IF NOT EXISTS idx_maintenance_date_time ON maintenance_entry(date_time);

-- If your existing table used INTEGER for processed_by/created_by, convert them to text-safe types
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'maintenance_entry' AND column_name = 'processed_by'
  ) THEN
    EXECUTE 'ALTER TABLE maintenance_entry ALTER COLUMN processed_by TYPE VARCHAR(128) USING processed_by::text';
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'maintenance_entry' AND column_name = 'created_by'
  ) THEN
    EXECUTE 'ALTER TABLE maintenance_entry ALTER COLUMN created_by TYPE VARCHAR(128) USING created_by::text';
  END IF;
END
$$;

-- Optional: keep `updated_at` current via trigger (Postgres)
-- Uncomment and enable if using PostgreSQL and want automatic updated_at maintenance.
--
-- CREATE OR REPLACE FUNCTION maintenance_entry_updated_at()
-- RETURNS TRIGGER AS $$
-- BEGIN
--   NEW.updated_at = now();
--   RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;
--
-- DROP TRIGGER IF EXISTS trg_maintenance_updated_at ON maintenance_entry;
-- CREATE TRIGGER trg_maintenance_updated_at
-- BEFORE UPDATE ON maintenance_entry
-- FOR EACH ROW EXECUTE PROCEDURE maintenance_entry_updated_at();

-- Note: `vehicle_id` was changed to VARCHAR(50) to allow alphanumeric IDs
-- (vehicles table uses TEXT/ VARCHAR for `vehicle_id`). If your DB already
-- has maintenance_entry with INTEGER vehicle_id, run the migration script
-- `migrate/0001_maintenance_vehicleid_to_text.sql` provided alongside.

