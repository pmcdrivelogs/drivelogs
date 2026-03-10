-- =====================================================
-- PARTS TABLE - For Part ID Generator
-- =====================================================
-- Run this script in Supabase SQL Editor
-- =====================================================

-- Create parts table for Part ID Generator
CREATE TABLE IF NOT EXISTS parts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    part_id VARCHAR(100) UNIQUE NOT NULL,
    part_name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    unit VARCHAR(50) DEFAULT 'Nos',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active'
);

-- Create index on part_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_parts_part_id ON parts(part_id);
CREATE INDEX IF NOT EXISTS idx_parts_part_name ON parts(part_name);

-- =====================================================
-- ALTER FUEL TABLE - Add Route ID, Vehicle ID, Mileage
-- =====================================================

-- Add route_id column
ALTER TABLE fuel ADD COLUMN IF NOT EXISTS route_id VARCHAR(50);

-- Add vehicle_id column
ALTER TABLE fuel ADD COLUMN IF NOT EXISTS vehicle_id VARCHAR(100);

-- Add vehicle_no column
ALTER TABLE fuel ADD COLUMN IF NOT EXISTS vehicle_no VARCHAR(100);

-- Add previous_km column (for mileage calculation)
ALTER TABLE fuel ADD COLUMN IF NOT EXISTS previous_km DECIMAL(12,2) DEFAULT 0;

-- Add current_km column
ALTER TABLE fuel ADD COLUMN IF NOT EXISTS current_km DECIMAL(12,2) DEFAULT 0;

-- Add mileage column (calculated: current_km - previous_km)
ALTER TABLE fuel ADD COLUMN IF NOT EXISTS mileage DECIMAL(12,2) DEFAULT 0;

-- Add mileage_per_liter column (calculated: mileage / quantity)
ALTER TABLE fuel ADD COLUMN IF NOT EXISTS mileage_per_liter DECIMAL(10,2) DEFAULT 0;

-- Create index on vehicle_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_fuel_vehicle_id ON fuel(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_fuel_route_id ON fuel(route_id);

-- =====================================================
-- VERIFY THE CHANGES
-- =====================================================
-- Check parts table:
-- SELECT * FROM parts LIMIT 10;

-- Check fuel table structure:
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'fuel' 
-- ORDER BY ordinal_position;
