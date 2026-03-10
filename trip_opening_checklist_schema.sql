-- Table for storing trip opening checklist records
CREATE TABLE IF NOT EXISTS trip_opening_checklist (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    registration_no TEXT,
    
    -- Checklist entry fields
    check_date DATE,
    check_time TIME,
    driver_name TEXT,
    kilometer_reading TEXT,
    fuel_level TEXT,
    engine_oil_level TEXT,
    radiator_water_level TEXT,
    vacuum_level TEXT,
    
    -- Tyre condition fields
    tyre_front_left TEXT,
    tyre_front_right TEXT,
    tyre_rear_lin TEXT,
    tyre_rear_lout TEXT,
    tyre_rear_rin TEXT,
    tyre_rear_rout TEXT,
    
    cleanliness_glass TEXT,
    remarks TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE CASCADE
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_trip_opening_checklist_vehicle_id ON trip_opening_checklist(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_trip_opening_checklist_date ON trip_opening_checklist(check_date);

-- Insert sample data for testing
INSERT INTO trip_opening_checklist (
    vehicle_id,
    registration_no,
    check_date,
    check_time,
    driver_name,
    kilometer_reading,
    fuel_level,
    engine_oil_level,
    radiator_water_level,
    vacuum_level,
    tyre_front_left,
    tyre_front_right,
    tyre_rear_lin,
    tyre_rear_lout,
    tyre_rear_rin,
    tyre_rear_rout,
    cleanliness_glass,
    remarks
) VALUES 
(
    'V001',
    'TN-01-AB-1234',
    '2025-12-17',
    '08:00:00',
    'John Driver',
    '12500',
    'Ok',
    'Ok',
    'Ok',
    'Ok',
    'Ok',
    'Ok',
    'Ok',
    'Ok',
    'Ok',
    'Ok',
    'Ok',
    'All systems good'
);
