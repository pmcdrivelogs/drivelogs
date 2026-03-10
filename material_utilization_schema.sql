-- =====================================================
-- MATERIAL UTILIZATION TABLE SCHEMA FOR SUPABASE
-- =====================================================
-- Table: material_utilization
-- Description: Stores material utilization records for vehicle maintenance
-- Reference: PMCTECH/LOGI/FORM 10/001
-- Integration: Parts are selected from 'purchases' table
--              Available quantity = purchased - issued - utilized
-- =====================================================

CREATE TABLE IF NOT EXISTS material_utilization (
    -- Primary Key
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Date & Time
    date_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Entry Number
    entry_no VARCHAR(100) NOT NULL UNIQUE,
    
    -- Vehicle Details
    vehicle_id VARCHAR(50) NOT NULL,
    vehicle_registration_no VARCHAR(50),
    
    -- Part Details
    part_no VARCHAR(100) NOT NULL,
    part_name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10, 2) NOT NULL,
    description TEXT,
    
    -- Personnel Details
    driver_id VARCHAR(50),
    mech_id VARCHAR(50),
    processed_by_id VARCHAR(50),
    
    -- Approval
    approved VARCHAR(10) CHECK (approved IN ('YES', 'NO')),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Index for faster lookup by entry number
CREATE INDEX IF NOT EXISTS idx_material_utilization_entry_no ON material_utilization(entry_no);

-- Index for date queries
CREATE INDEX IF NOT EXISTS idx_material_utilization_date ON material_utilization(date_time);

-- Index for vehicle queries
CREATE INDEX IF NOT EXISTS idx_material_utilization_vehicle_id ON material_utilization(vehicle_id);

-- Index for part queries
CREATE INDEX IF NOT EXISTS idx_material_utilization_part_no ON material_utilization(part_no);

-- Index for created_at queries
CREATE INDEX IF NOT EXISTS idx_material_utilization_created_at ON material_utilization(created_at);

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_material_utilization_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_material_utilization_updated_at
    BEFORE UPDATE ON material_utilization
    FOR EACH ROW
    EXECUTE FUNCTION update_material_utilization_updated_at();

-- Function to get next entry number
CREATE OR REPLACE FUNCTION get_next_material_utilization_entry_no()
RETURNS TEXT AS $$
DECLARE
    next_num INTEGER;
    next_entry_no TEXT;
BEGIN
    SELECT COALESCE(MAX(CAST(SUBSTRING(entry_no FROM 'UTI/([0-9]+)/') AS INTEGER)), 2525) + 1
    INTO next_num
    FROM material_utilization;
    
    next_entry_no := 'PMCTECH/LOGI/UTI/' || next_num || '/001';
    RETURN next_entry_no;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable Row Level Security
ALTER TABLE material_utilization ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Allow all access to material utilization records" ON material_utilization;

-- Create policy to allow all operations
CREATE POLICY "Allow all access to material utilization records"
    ON material_utilization
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to authenticated users
GRANT ALL ON material_utilization TO authenticated;
GRANT ALL ON material_utilization TO anon;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE material_utilization IS 'Stores material utilization records for vehicle maintenance';
COMMENT ON COLUMN material_utilization.date_time IS 'Date and time when material was utilized';
COMMENT ON COLUMN material_utilization.entry_no IS 'Unique utilization entry number';
COMMENT ON COLUMN material_utilization.vehicle_id IS 'Vehicle identification number';
COMMENT ON COLUMN material_utilization.vehicle_registration_no IS 'Vehicle registration number';
COMMENT ON COLUMN material_utilization.part_no IS 'Part number being utilized';
COMMENT ON COLUMN material_utilization.part_name IS 'Name of the part';
COMMENT ON COLUMN material_utilization.quantity IS 'Quantity of material used';
COMMENT ON COLUMN material_utilization.description IS 'Detailed description of utilization';
COMMENT ON COLUMN material_utilization.driver_id IS 'Driver identification number';
COMMENT ON COLUMN material_utilization.mech_id IS 'Mechanic identification number';
COMMENT ON COLUMN material_utilization.processed_by_id IS 'ID of person who processed the record';
COMMENT ON COLUMN material_utilization.approved IS 'Approval status (YES/NO)';
