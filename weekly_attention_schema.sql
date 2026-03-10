-- Create weekly_attention table
CREATE TABLE public.weekly_attention (
  id SERIAL NOT NULL,
  vehicle_id TEXT NULL,
  registration_no TEXT NULL,
  process_name TEXT NULL,
  week1_date DATE NULL,
  week1_km TEXT NULL,
  week1_obs TEXT NULL,
  week2_date DATE NULL,
  week2_km TEXT NULL,
  week2_obs TEXT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT weekly_attention_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_weekly_attention_vehicle_id ON public.weekly_attention USING btree (vehicle_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_weekly_attention_week1_date ON public.weekly_attention USING btree (week1_date) TABLESPACE pg_default;

-- Sample INSERT for testing
INSERT INTO public.weekly_attention (
  vehicle_id, registration_no, process_name,
  week1_date, week1_km, week1_obs,
  week2_date, week2_km, week2_obs
) VALUES (
  'V001', 'TN01AB1234', 'FLOOR BROOMING',
  '2025-12-17', '50000', 'Completed',
  '2025-12-24', '50200', 'Completed'
);
