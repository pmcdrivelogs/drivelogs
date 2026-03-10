-- Annual Maintenance (17000 KM) Checklist Schema
-- This table stores annual/17000km periodic maintenance records by technicians

CREATE TABLE IF NOT EXISTS public.annual_maintenance (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    registration_no TEXT NOT NULL,
    from_month TEXT NOT NULL,
    to_month TEXT NOT NULL,
    
    -- Process 1: PUMP OIL ATTACHMENT
    processed_date_1 DATE,
    kilometer_reading_1 TEXT,
    action_processed_1 TEXT,
    observation_1 TEXT,
    parts_used_1 TEXT,
    qty_1 TEXT,
    supplier_bill_1 TEXT,
    value_1 TEXT,
    
    -- Process 2: CROWN VALIDE ADJUSTMENT
    processed_date_2 DATE,
    kilometer_reading_2 TEXT,
    action_processed_2 TEXT,
    observation_2 TEXT,
    parts_used_2 TEXT,
    qty_2 TEXT,
    supplier_bill_2 TEXT,
    value_2 TEXT,
    
    -- Process 3: DRIVE LINE REPLACEMENT
    processed_date_3 DATE,
    kilometer_reading_3 TEXT,
    action_processed_3 TEXT,
    observation_3 TEXT,
    parts_used_3 TEXT,
    qty_3 TEXT,
    supplier_bill_3 TEXT,
    value_3 TEXT,
    
    -- Process 4: CLUTCH FREE ADJUSTMENT
    processed_date_4 DATE,
    kilometer_reading_4 TEXT,
    action_processed_4 TEXT,
    observation_4 TEXT,
    parts_used_4 TEXT,
    qty_4 TEXT,
    supplier_bill_4 TEXT,
    value_4 TEXT,
    
    -- Process 5: PROGRESSIVE BRAKING FOR ACCIDENT
    processed_date_5 DATE,
    kilometer_reading_5 TEXT,
    action_processed_5 TEXT,
    observation_5 TEXT,
    parts_used_5 TEXT,
    qty_5 TEXT,
    supplier_bill_5 TEXT,
    value_5 TEXT,
    
    -- Process 6: TYRE REFINING
    processed_date_6 DATE,
    kilometer_reading_6 TEXT,
    action_processed_6 TEXT,
    observation_6 TEXT,
    parts_used_6 TEXT,
    qty_6 TEXT,
    supplier_bill_6 TEXT,
    value_6 TEXT,
    
    -- Process 7: BREAK OIL CHECKING OR REPLACEMENT
    processed_date_7 DATE,
    kilometer_reading_7 TEXT,
    action_processed_7 TEXT,
    observation_7 TEXT,
    parts_used_7 TEXT,
    qty_7 TEXT,
    supplier_bill_7 TEXT,
    value_7 TEXT,
    
    -- Process 8: BRAKE CHAMBER FUNCTIONS & VALVE CHECKING
    processed_date_8 DATE,
    kilometer_reading_8 TEXT,
    action_processed_8 TEXT,
    observation_8 TEXT,
    parts_used_8 TEXT,
    qty_8 TEXT,
    supplier_bill_8 TEXT,
    value_8 TEXT,
    
    -- Process 9: BREAK TIMING & POWER CHAMBER OPENING & AIR LEAKMENT
    processed_date_9 DATE,
    kilometer_reading_9 TEXT,
    action_processed_9 TEXT,
    observation_9 TEXT,
    parts_used_9 TEXT,
    qty_9 TEXT,
    supplier_bill_9 TEXT,
    value_9 TEXT,
    
    -- Process 10: CLUTCH RELEASE & REPAIR OR REPLACEMENT
    processed_date_10 DATE,
    kilometer_reading_10 TEXT,
    action_processed_10 TEXT,
    observation_10 TEXT,
    parts_used_10 TEXT,
    qty_10 TEXT,
    supplier_bill_10 TEXT,
    value_10 TEXT,
    
    -- Process 11: RADIATOR COOLANT BAR LEAKMENT
    processed_date_11 DATE,
    kilometer_reading_11 TEXT,
    action_processed_11 TEXT,
    observation_11 TEXT,
    parts_used_11 TEXT,
    qty_11 TEXT,
    supplier_bill_11 TEXT,
    value_11 TEXT,
    
    -- Process 12: SIGNAL ON EXPRESS LIGHT, AIR CHECKS & REPLACEMENT
    processed_date_12 DATE,
    kilometer_reading_12 TEXT,
    action_processed_12 TEXT,
    observation_12 TEXT,
    parts_used_12 TEXT,
    qty_12 TEXT,
    supplier_bill_12 TEXT,
    value_12 TEXT,
    
    -- Process 13: AIR COMPRESSOR AIR SUPPLY CONDITIONUNG EQUIPMT & SERVICE
    processed_date_13 DATE,
    kilometer_reading_13 TEXT,
    action_processed_13 TEXT,
    observation_13 TEXT,
    parts_used_13 TEXT,
    qty_13 TEXT,
    supplier_bill_13 TEXT,
    value_13 TEXT,
    
    -- Process 14: AIR FILTER REPLACEMENT
    processed_date_14 DATE,
    kilometer_reading_14 TEXT,
    action_processed_14 TEXT,
    observation_14 TEXT,
    parts_used_14 TEXT,
    qty_14 TEXT,
    supplier_bill_14 TEXT,
    value_14 TEXT,
    
    -- Process 15: VACCUUM STAER OIL &SL TAILIED
    processed_date_15 DATE,
    kilometer_reading_15 TEXT,
    action_processed_15 TEXT,
    observation_15 TEXT,
    parts_used_15 TEXT,
    qty_15 TEXT,
    supplier_bill_15 TEXT,
    value_15 TEXT,
    
    -- Process 16: WATER PUMP CONDTION & CHECKING
    processed_date_16 DATE,
    kilometer_reading_16 TEXT,
    action_processed_16 TEXT,
    observation_16 TEXT,
    parts_used_16 TEXT,
    qty_16 TEXT,
    supplier_bill_16 TEXT,
    value_16 TEXT,
    
    -- Process 17: VEHICLE ATTACHMENTS
    processed_date_17 DATE,
    kilometer_reading_17 TEXT,
    action_processed_17 TEXT,
    observation_17 TEXT,
    parts_used_17 TEXT,
    qty_17 TEXT,
    supplier_bill_17 TEXT,
    value_17 TEXT,
    
    -- Process 18: GAS FILTER SERVICE
    processed_date_18 DATE,
    kilometer_reading_18 TEXT,
    action_processed_18 TEXT,
    observation_18 TEXT,
    parts_used_18 TEXT,
    qty_18 TEXT,
    supplier_bill_18 TEXT,
    value_18 TEXT,
    
    -- Process 19: TOTAL AIR BOOT WORK (60+C)
    processed_date_19 DATE,
    kilometer_reading_19 TEXT,
    action_processed_19 TEXT,
    observation_19 TEXT,
    parts_used_19 TEXT,
    qty_19 TEXT,
    supplier_bill_19 TEXT,
    value_19 TEXT,
    
    -- Process 20: TOTAL ELECTRICAL CIRCUIT & TIMING
    processed_date_20 DATE,
    kilometer_reading_20 TEXT,
    action_processed_20 TEXT,
    observation_20 TEXT,
    parts_used_20 TEXT,
    qty_20 TEXT,
    supplier_bill_20 TEXT,
    value_20 TEXT,
    
    -- Process 21: TOTAL LIGHTS & ACTIVE CHECKING
    processed_date_21 DATE,
    kilometer_reading_21 TEXT,
    action_processed_21 TEXT,
    observation_21 TEXT,
    parts_used_21 TEXT,
    qty_21 TEXT,
    supplier_bill_21 TEXT,
    value_21 TEXT,
    
    -- Process 22: TTV ALL WHEELS BEARING ACCOUNT SET REPLACEMENT
    processed_date_22 DATE,
    kilometer_reading_22 TEXT,
    action_processed_22 TEXT,
    observation_22 TEXT,
    parts_used_22 TEXT,
    qty_22 TEXT,
    supplier_bill_22 TEXT,
    value_22 TEXT,
    
    -- Process 23: FUEL PUMP & CONATCT BALL POWER SYSTEM
    processed_date_23 DATE,
    kilometer_reading_23 TEXT,
    action_processed_23 TEXT,
    observation_23 TEXT,
    parts_used_23 TEXT,
    qty_23 TEXT,
    supplier_bill_23 TEXT,
    value_23 TEXT,
    
    -- Process 24: MAGNETO SET TIMICING
    processed_date_24 DATE,
    kilometer_reading_24 TEXT,
    action_processed_24 TEXT,
    observation_24 TEXT,
    parts_used_24 TEXT,
    qty_24 TEXT,
    supplier_bill_24 TEXT,
    value_24 TEXT,
    
    -- Process 25: IMPTVEMENT BATTERY CHARGING & TEST FILING
    processed_date_25 DATE,
    kilometer_reading_25 TEXT,
    action_processed_25 TEXT,
    observation_25 TEXT,
    parts_used_25 TEXT,
    qty_25 TEXT,
    supplier_bill_25 TEXT,
    value_25 TEXT,
    
    -- Process 26: FIRST AID KIT CHECKING
    processed_date_26 DATE,
    kilometer_reading_26 TEXT,
    action_processed_26 TEXT,
    observation_26 TEXT,
    parts_used_26 TEXT,
    qty_26 TEXT,
    supplier_bill_26 TEXT,
    value_26 TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_annual_maintenance_vehicle_id ON public.annual_maintenance(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_annual_maintenance_from_month ON public.annual_maintenance(from_month);

-- Sample insert statement
INSERT INTO public.annual_maintenance (
    vehicle_id, registration_no, from_month, to_month,
    processed_date_1, kilometer_reading_1, action_processed_1, observation_1, parts_used_1, qty_1, supplier_bill_1, value_1,
    processed_date_2, kilometer_reading_2, action_processed_2, observation_2, parts_used_2, qty_2, supplier_bill_2, value_2
) VALUES (
    'V001', 'TN01AB1234', 'April', 'September',
    '2024-09-30', '17000', 'Oil checked and replaced', 'Functioning properly', 'Pump Oil', '1L', 'BILL001/30-09-2024', '₹300',
    '2024-09-30', '17000', 'Adjusted crown valve', 'Working smoothly', 'Valve parts', '1', 'BILL002/30-09-2024', '₹500'
);
