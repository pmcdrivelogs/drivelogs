CREATE TABLE public.driver_voice (
  id SERIAL NOT NULL,
  vehicle_id TEXT NULL,
  registration_no TEXT NULL,
  date DATE NULL,
  time TIME NULL,
  complaints TEXT NULL,
  suggestions TEXT NULL,
  driver_name TEXT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT driver_voice_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_driver_voice_vehicle_id ON public.driver_voice USING btree (vehicle_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_driver_voice_date ON public.driver_voice USING btree (date) TABLESPACE pg_default;

-- Sample INSERT
INSERT INTO public.driver_voice (vehicle_id, registration_no, date, time, complaints, suggestions, driver_name)
VALUES ('V001', 'TN01AB1234', '2024-01-15', '10:30:00', 'Engine making unusual noise', 'Check engine immediately', 'John Doe');
