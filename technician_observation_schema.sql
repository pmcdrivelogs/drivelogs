-- Table for Technician Observations (Complaints & Works)
CREATE TABLE public.technician_observation_works (
  id SERIAL NOT NULL,
  vehicle_id TEXT NULL,
  registration_no TEXT NULL,
  date DATE NULL,
  time TIME NULL,
  complaints TEXT NULL,
  works TEXT NULL,
  ta_name TEXT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT technician_observation_works_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_tech_obs_works_vehicle_id ON public.technician_observation_works USING btree (vehicle_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_tech_obs_works_date ON public.technician_observation_works USING btree (date) TABLESPACE pg_default;

-- Table for Technician Materials & Estimation
CREATE TABLE public.technician_observation_materials (
  id SERIAL NOT NULL,
  vehicle_id TEXT NULL,
  registration_no TEXT NULL,
  date DATE NULL,
  time TIME NULL,
  materials TEXT NULL,
  estimation TEXT NULL,
  ta_name TEXT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT technician_observation_materials_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_tech_obs_mat_vehicle_id ON public.technician_observation_materials USING btree (vehicle_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_tech_obs_mat_date ON public.technician_observation_materials USING btree (date) TABLESPACE pg_default;

-- Sample INSERTs
INSERT INTO public.technician_observation_works (vehicle_id, registration_no, date, time, complaints, works, ta_name)
VALUES ('V001', 'TN01AB1234', '2024-01-15', '10:30:00', 'Engine overheating', 'Check coolant system', 'Technician A');

INSERT INTO public.technician_observation_materials (vehicle_id, registration_no, date, time, materials, estimation, ta_name)
VALUES ('V001', 'TN01AB1234', '2024-01-15', '11:00:00', 'Coolant fluid, radiator hose', '₹2500', 'Technician A');
