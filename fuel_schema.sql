-- Fuel Table Schema for Supabase
-- Run this in your Supabase SQL Editor

CREATE TABLE fuel (
  id SERIAL PRIMARY KEY,
  date DATE,
  time TEXT,
  entry_no TEXT,
  bill_no TEXT,
  type_of_purchase TEXT,
  part_no TEXT,
  part_name TEXT,
  quantity NUMERIC(10, 2),
  rate NUMERIC(10, 2),
  amount NUMERIC(12, 2),
  rate_id TEXT,
  vehicle_reg_no TEXT,
  km_reading NUMERIC(12, 2),
  mileage NUMERIC(8, 2),
  driver TEXT,
  user_id UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX idx_fuel_entry_no ON fuel(entry_no);
CREATE INDEX idx_fuel_date ON fuel(date);
CREATE INDEX idx_fuel_vehicle_reg_no ON fuel(vehicle_reg_no);

-- Enable Row Level Security (optional)
-- ALTER TABLE fuel ENABLE ROW LEVEL SECURITY;
