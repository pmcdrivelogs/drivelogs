-- =====================================================
-- TRIP SHEET TABLE SCHEMA FOR SUPABASE
-- =====================================================
-- Table: trip_sheet
-- Description: Stores all trip records with driver, vehicle, and passenger details
-- Reference: PMCTECH/LOGI/FORM 8/001
-- =====================================================

CREATE TABLE IF NOT EXISTS trip_sheet (
    -- Primary Key
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Date & Time
    date_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Driver Details
    driver_id VARCHAR(50) NOT NULL,
    driver_name VARCHAR(255) NOT NULL,
    
    -- Vehicle Details
    vehicle_id VARCHAR(50) NOT NULL,
    vehicle_no VARCHAR(50),
    
    -- Trip Kilometer Details
    trip_start_km DECIMAL(10, 2) NOT NULL,
    trip_close_km DECIMAL(10, 2) NOT NULL,
    trip_distance DECIMAL(10, 2) GENERATED ALWAYS AS (trip_close_km - trip_start_km) STORED,
    
    -- Trip Time Details
    trip_start_time TIME NOT NULL,
    trip_close_time TIME NOT NULL,
    
    -- Passenger Details (Cumulative Strength)
    male_count INTEGER NOT NULL DEFAULT 0,
    female_count INTEGER NOT NULL DEFAULT 0,
    transgender_count INTEGER NOT NULL DEFAULT 0,
    total_strength INTEGER GENERATED ALWAYS AS (male_count + female_count + transgender_count) STORED,
    
    -- Location Details
    trip_start_place VARCHAR(255) NOT NULL,
    trip_close_place VARCHAR(255) NOT NULL,
    
    -- Additional Info
    comments TEXT,
    entered_by VARCHAR(255) NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Index for faster lookup by date
CREATE INDEX IF NOT EXISTS idx_trip_sheet_date ON trip_sheet(date_time);

-- Index for driver queries
CREATE INDEX IF NOT EXISTS idx_trip_sheet_driver_id ON trip_sheet(driver_id);

-- Index for vehicle queries
CREATE INDEX IF NOT EXISTS idx_trip_sheet_vehicle_id ON trip_sheet(vehicle_id);

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_trip_sheet_created_at ON trip_sheet(created_at);

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_trip_sheet_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_trip_sheet_updated_at
    BEFORE UPDATE ON trip_sheet
    FOR EACH ROW
    EXECUTE FUNCTION update_trip_sheet_updated_at();

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable Row Level Security
ALTER TABLE trip_sheet ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Allow all access to trip sheet records" ON trip_sheet;

-- Create policy to allow all operations
CREATE POLICY "Allow all access to trip sheet records"
    ON trip_sheet
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to authenticated users
GRANT ALL ON trip_sheet TO authenticated;
GRANT ALL ON trip_sheet TO anon;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE trip_sheet IS 'Stores trip records with driver, vehicle, and passenger details';
COMMENT ON COLUMN trip_sheet.date_time IS 'Date and time when trip sheet was filled';
COMMENT ON COLUMN trip_sheet.driver_id IS 'Driver identification number';
COMMENT ON COLUMN trip_sheet.driver_name IS 'Full name of the driver';
COMMENT ON COLUMN trip_sheet.vehicle_id IS 'Vehicle identification number';
COMMENT ON COLUMN trip_sheet.vehicle_no IS 'Vehicle registration number';
COMMENT ON COLUMN trip_sheet.trip_start_km IS 'Kilometer reading at trip start';
COMMENT ON COLUMN trip_sheet.trip_close_km IS 'Kilometer reading at trip end';
COMMENT ON COLUMN trip_sheet.trip_distance IS 'Calculated trip distance (auto-computed)';
COMMENT ON COLUMN trip_sheet.trip_start_time IS 'Time when trip started';
COMMENT ON COLUMN trip_sheet.trip_close_time IS 'Time when trip ended';
COMMENT ON COLUMN trip_sheet.male_count IS 'Number of male students/faculty';
COMMENT ON COLUMN trip_sheet.female_count IS 'Number of female students/faculty';
COMMENT ON COLUMN trip_sheet.transgender_count IS 'Number of transgender students/faculty';
COMMENT ON COLUMN trip_sheet.total_strength IS 'Total number of students and faculty (auto-calculated)';
COMMENT ON COLUMN trip_sheet.trip_start_place IS 'Starting location of the trip';
COMMENT ON COLUMN trip_sheet.trip_close_place IS 'Ending location of the trip';
COMMENT ON COLUMN trip_sheet.comments IS 'Any additional comments or remarks';
COMMENT ON COLUMN trip_sheet.entered_by IS 'Name of person who entered the record';
