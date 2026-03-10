-- Migration: backfill maintenance_entry.vehicle_id from vehicles table using registration_no
-- Run this after converting maintenance_entry.vehicle_id to VARCHAR (0001_maintenance_vehicleid_to_text.sql).
-- This will populate vehicle_id where it's currently NULL but registration_no matches a vehicle.

BEGIN;

-- Update maintenance entries that lack vehicle_id but have a registration_no
UPDATE maintenance_entry m
SET vehicle_id = v.vehicle_id
FROM vehicles v
WHERE (m.vehicle_id IS NULL OR trim(m.vehicle_id) = '')
  AND m.registration_no IS NOT NULL
  AND trim(m.registration_no) = trim(v.registration_no);

COMMIT;

-- After running this, maintenance entries whose registration numbers match a vehicle
-- will have their vehicle_id set to the vehicle's id (including alphanumeric ids like '96E').
