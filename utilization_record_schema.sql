-- Create utilization_record table
CREATE TABLE public.utilization_record (
  id SERIAL NOT NULL,
  vehicle_id TEXT NOT NULL,
  registration_no TEXT NULL,
  opening_time DATE NULL,
  opening_kilometer TEXT NULL,
  opening_place TEXT NULL,
  purpose_trip TEXT NULL,
  strength_she TEXT NULL,
  strength_he TEXT NULL,
  closing_time TIME WITHOUT TIME ZONE NULL,
  closing_kilometer TEXT NULL,
  closing_place TEXT NULL,
  coverage_time TEXT NULL,
  coverage_kms TEXT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT utilization_record_pkey PRIMARY KEY (id),
  CONSTRAINT utilization_record_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES vehicles (vehicle_id) ON DELETE CASCADE
) TABLESPACE pg_default;

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_utilization_record_vehicle_id ON public.utilization_record USING btree (vehicle_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_utilization_record_date ON public.utilization_record USING btree (opening_time) TABLESPACE pg_default;

-- Sample INSERT for testing
INSERT INTO public.utilization_record (
  vehicle_id, registration_no, opening_time, opening_kilometer, opening_place,
  purpose_trip, strength_she, strength_he, closing_time, closing_kilometer,
  closing_place, coverage_time, coverage_kms
) VALUES (
  'V001', 'TN01AB1234', '2025-12-17', '50000', 'PMC College',
  'Student Transport', '45', '30', '17:30:00', '50175',
  'PMC College', '7:30', '175'
);
