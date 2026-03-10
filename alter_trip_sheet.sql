-- =====================================================
-- ALTER TRIP SHEET TABLE - ADD ROUTE_ID AND DETAILED STRENGTH COUNTS
-- =====================================================
-- Run this script in Supabase SQL Editor
-- =====================================================

-- Step 1: Add route_id column
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS route_id VARCHAR(50);

-- Step 2: Add Student counts
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS student_male INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS student_female INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS student_transgender INTEGER DEFAULT 0;

-- Step 3: Add Faculty counts
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS faculty_male INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS faculty_female INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS faculty_transgender INTEGER DEFAULT 0;

-- Step 4: Add Guest counts
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS guest_male INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS guest_female INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN IF NOT EXISTS guest_transgender INTEGER DEFAULT 0;

-- Step 5: Drop existing generated columns if they exist (they block inserts)
ALTER TABLE trip_sheet DROP COLUMN IF EXISTS student_total;
ALTER TABLE trip_sheet DROP COLUMN IF EXISTS faculty_total;
ALTER TABLE trip_sheet DROP COLUMN IF EXISTS guest_total;
ALTER TABLE trip_sheet DROP COLUMN IF EXISTS cumulative_strength;

-- Step 6: Recreate as regular columns
ALTER TABLE trip_sheet ADD COLUMN student_total INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN faculty_total INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN guest_total INTEGER DEFAULT 0;
ALTER TABLE trip_sheet ADD COLUMN cumulative_strength INTEGER DEFAULT 0;

-- Step 7: Create index on route_id for faster filtering
CREATE INDEX IF NOT EXISTS idx_trip_sheet_route_id ON trip_sheet(route_id);

-- =====================================================
-- VERIFY THE CHANGES
-- =====================================================
-- Run this to check the table structure:
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'trip_sheet' 
-- ORDER BY ordinal_position;
