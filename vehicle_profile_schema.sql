-- Table for storing vehicle basic information
CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT UNIQUE NOT NULL,
    registration_no TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing annual records for each vehicle
CREATE TABLE IF NOT EXISTS vehicle_annual_records (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    registration_no TEXT,
    
    -- FITNESS CERTIFICATE (Row 1)
    fitness_due_date DATE,
    fitness_executed_date DATE,
    fitness_next_due_date DATE,
    fitness_invoice TEXT,
    fitness_expenditure TEXT,
    fitness_remarks TEXT,
    
    -- INSURANCE (Row 2)
    insurance_due_date DATE,
    insurance_executed_date DATE,
    insurance_next_due_date DATE,
    insurance_invoice TEXT,
    insurance_expenditure TEXT,
    insurance_remarks TEXT,
    
    -- ROAD TAX 1 QL (Row 3)
    tax1_due_date DATE,
    tax1_executed_date DATE,
    tax1_next_due_date DATE,
    tax1_invoice TEXT,
    tax1_expenditure TEXT,
    tax1_remarks TEXT,
    
    -- ROAD TAX 2 QL (Row 4)
    tax2_due_date DATE,
    tax2_executed_date DATE,
    tax2_next_due_date DATE,
    tax2_invoice TEXT,
    tax2_expenditure TEXT,
    tax2_remarks TEXT,
    
    -- ROAD TAX 3 QL (Row 5)
    tax3_due_date DATE,
    tax3_executed_date DATE,
    tax3_next_due_date DATE,
    tax3_invoice TEXT,
    tax3_expenditure TEXT,
    tax3_remarks TEXT,
    
    -- ROAD TAX 4 QL (Row 6)
    tax4_due_date DATE,
    tax4_executed_date DATE,
    tax4_next_due_date DATE,
    tax4_invoice TEXT,
    tax4_expenditure TEXT,
    tax4_remarks TEXT,
    
    -- ROUTE PERMIT (Row 7)
    permit_due_date DATE,
    permit_executed_date DATE,
    permit_next_due_date DATE,
    permit_invoice TEXT,
    permit_expenditure TEXT,
    permit_remarks TEXT,
    
    -- EMISSION TEST 1 HALF (Row 8)
    emission1_due_date DATE,
    emission1_executed_date DATE,
    emission1_next_due_date DATE,
    emission1_invoice TEXT,
    emission1_expenditure TEXT,
    emission1_remarks TEXT,
    
    -- EMISSION TEST 2 HALF (Row 9)
    emission2_due_date DATE,
    emission2_executed_date DATE,
    emission2_next_due_date DATE,
    emission2_invoice TEXT,
    emission2_expenditure TEXT,
    emission2_remarks TEXT,
    
    -- SPEED GOVERNER ANNUAL CALIBRATION (Row 10)
    speed_due_date DATE,
    speed_executed_date DATE,
    speed_next_due_date DATE,
    speed_invoice TEXT,
    speed_expenditure TEXT,
    speed_remarks TEXT,
    
    -- FIRE EXTINGUISHER REFIL (Row 11)
    fire_due_date DATE,
    fire_executed_date DATE,
    fire_next_due_date DATE,
    fire_invoice TEXT,
    fire_expenditure TEXT,
    fire_remarks TEXT,
    
    -- FIRST AID REPLACEMENT (Row 12)
    firstaid_due_date DATE,
    firstaid_executed_date DATE,
    firstaid_next_due_date DATE,
    firstaid_invoice TEXT,
    firstaid_expenditure TEXT,
    firstaid_remarks TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE CASCADE
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_vehicle_annual_records_vehicle_id ON vehicle_annual_records(vehicle_id);

-- Insert sample vehicles for testing
INSERT INTO vehicles (vehicle_id, registration_no) VALUES 
('V001', 'TN-01-AB-1234'),
('V002', 'TN-02-CD-5678'),
('V003', 'TN-03-EF-9012')
ON CONFLICT (vehicle_id) DO NOTHING;
