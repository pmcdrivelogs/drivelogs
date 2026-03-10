-- Table for storing permanent vehicle records
CREATE TABLE IF NOT EXISTS vehicle_permanent_records (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT UNIQUE NOT NULL,
    registration_no TEXT,
    
    -- Permanent Record Fields (12 fields)
    registration_number TEXT,
    route_id TEXT,
    vehicle_type TEXT,
    managing_college TEXT,
    make TEXT,
    modal TEXT,
    year_manufacturing TEXT,
    year_purchasing TEXT,
    engine_number TEXT,
    
    chassis_number TEXT,
    speed_governer_id TEXT,
    seating_capacity TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE CASCADE
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_vehicle_permanent_records_vehicle_id ON vehicle_permanent_records(vehicle_id);

-- Insert sample permanent records for testing
INSERT INTO vehicle_permanent_records (
    vehicle_id, 
    registration_no, 
    registration_number,
    route_id,
    vehicle_type,
    managing_college,
    seating_capacity
) VALUES 
(
    'V001', 
    'TN-01-AB-1234',
    'TN-01-AB-1234',
    'R001',
    'Bus',
    'PSG College of Technology',
    '40'
),
(
    'V002', 
    'TN-02-CD-5678',
    'TN-02-CD-5678',
    'R002',
    'Bus',
    'PSG College of Arts & Science',
    '35'
),
(
    'V003', 
    'TN-03-EF-9012',
    'TN-03-EF-9012',
    'R003',
    'Bus',
    'PSG Institute of Management',
    '45'
)
ON CONFLICT (vehicle_id) DO NOTHING;
