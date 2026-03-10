-- Monthly Maintenance (5000 KM) Checklist Schema
-- This table stores monthly/5000km periodic maintenance records by technicians

CREATE TABLE IF NOT EXISTS public.monthly_maintenance (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    registration_no TEXT NOT NULL,
    month TEXT NOT NULL,
    
    -- Process 1: FUEL PUMP OIL CHECKUP
    processed_date_1 DATE,
    kilometer_reading_1 TEXT,
    action_processed_1 TEXT,
    observation_1 TEXT,
    parts_used_1 TEXT,
    qty_1 TEXT,
    supplier_bill_1 TEXT,
    value_1 TEXT,
    
    -- Process 2: AIR CLEANER OIL CHECKUP
    processed_date_2 DATE,
    kilometer_reading_2 TEXT,
    action_processed_2 TEXT,
    observation_2 TEXT,
    parts_used_2 TEXT,
    qty_2 TEXT,
    supplier_bill_2 TEXT,
    value_2 TEXT,
    
    -- Process 3: AIR CLEANER STAINER CHECKUP
    processed_date_3 DATE,
    kilometer_reading_3 TEXT,
    action_processed_3 TEXT,
    observation_3 TEXT,
    parts_used_3 TEXT,
    qty_3 TEXT,
    supplier_bill_3 TEXT,
    value_3 TEXT,
    
    -- Process 4: JOINT TIE ROD & ENDS CHECKUP
    processed_date_4 DATE,
    kilometer_reading_4 TEXT,
    action_processed_4 TEXT,
    observation_4 TEXT,
    parts_used_4 TEXT,
    qty_4 TEXT,
    supplier_bill_4 TEXT,
    value_4 TEXT,
    
    -- Process 5: UNLOAD KIT SERVICE
    processed_date_5 DATE,
    kilometer_reading_5 TEXT,
    action_processed_5 TEXT,
    observation_5 TEXT,
    parts_used_5 TEXT,
    qty_5 TEXT,
    supplier_bill_5 TEXT,
    value_5 TEXT,
    
    -- Process 6: VEHICLE START & ENGINE NOICE OBSERVATION
    processed_date_6 DATE,
    kilometer_reading_6 TEXT,
    action_processed_6 TEXT,
    observation_6 TEXT,
    parts_used_6 TEXT,
    qty_6 TEXT,
    supplier_bill_6 TEXT,
    value_6 TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_monthly_maintenance_vehicle_id ON public.monthly_maintenance(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_monthly_maintenance_month ON public.monthly_maintenance(month);

-- Sample insert statement
INSERT INTO public.monthly_maintenance (
    vehicle_id, registration_no, month,
    processed_date_1, kilometer_reading_1, action_processed_1, observation_1, parts_used_1, qty_1, supplier_bill_1, value_1,
    processed_date_2, kilometer_reading_2, action_processed_2, observation_2, parts_used_2, qty_2, supplier_bill_2, value_2
) VALUES (
    'V001', 'TN01AB1234', 'January',
    '2024-01-15', '5000', 'Checked and topped up', 'Oil level normal', 'Pump Oil', '0.5L', 'BILL001/15-01-2024', '₹250',
    '2024-01-15', '5000', 'Cleaned and refilled', 'Filter cleaned', 'Air Filter Oil', '0.3L', 'BILL002/15-01-2024', '₹150'
);
