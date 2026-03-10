-- Create fuel_consumption table
CREATE TABLE public.fuel_consumption (
  id SERIAL NOT NULL,
  vehicle_id TEXT NULL,
  registration_no TEXT NULL,
  route_id TEXT NULL,
  make_model TEXT NULL,
  intend_no TEXT NULL,
  date DATE NULL,
  bill_no TEXT NULL,
  bill_date DATE NULL,
  bunk_name TEXT NULL,
  qty TEXT NULL,
  rate TEXT NULL,
  amount TEXT NULL,
  km_reading TEXT NULL,
  driver_name TEXT NULL,
  remarks TEXT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fuel_consumption_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_fuel_consumption_vehicle_id ON public.fuel_consumption USING btree (vehicle_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_fuel_consumption_registration ON public.fuel_consumption USING btree (registration_no) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_fuel_consumption_date ON public.fuel_consumption USING btree (date) TABLESPACE pg_default;

-- Sample INSERT for testing
INSERT INTO public.fuel_consumption (
  vehicle_id, registration_no, route_id, make_model, intend_no, date, bill_no,
  bill_date, bunk_name, qty, rate, amount, km_reading, driver_name, remarks
) VALUES (
  'V001', 'TN01AB1234', 'R001', 'Tata Starbus', '1', '2025-12-17', 'BILL2025001',
  '2025-12-17', 'Indian Oil Petrol Pump', '50', '102.50', '5125', '50000', 'John Doe', 'Regular refill'
);
