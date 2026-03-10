-- Create daily_technical_remarks table
CREATE TABLE public.daily_technical_remarks (
  id SERIAL NOT NULL,
  vehicle_id TEXT NULL,
  registration_no TEXT NULL,
  date DATE NULL,
  kilometer TEXT NULL,
  drivers_voice TEXT NULL,
  technical_observation TEXT NULL,
  day_end_status TEXT NULL,
  materials_purchased TEXT NULL,
  supplier_bill TEXT NULL,
  amount TEXT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT daily_technical_remarks_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_daily_technical_remarks_vehicle_id ON public.daily_technical_remarks USING btree (vehicle_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_daily_technical_remarks_date ON public.daily_technical_remarks USING btree (date) TABLESPACE pg_default;

-- Sample INSERT for testing
INSERT INTO public.daily_technical_remarks (
  vehicle_id, registration_no, date, kilometer, drivers_voice,
  technical_observation, day_end_status, materials_purchased,
  supplier_bill, amount
) VALUES (
  'V001', 'TN01AB1234', '2025-12-17', '50000', 'No work',
  'Regular inspection completed. All systems working properly.',
  'Arrested', 'Engine oil, Air filter',
  'ABC Parts/BILL001/17-12-2025', '2500'
);
