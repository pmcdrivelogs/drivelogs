CREATE TABLE public.process_of_works (
  id SERIAL NOT NULL,
  vehicle_id TEXT NULL,
  registration_no TEXT NULL,
  date DATE NULL,
  time TIME NULL,
  nature_of_work TEXT NULL,
  rectified_results TEXT NULL,
  bill_no TEXT NULL,
  amount TEXT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT process_of_works_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_process_works_vehicle_id ON public.process_of_works USING btree (vehicle_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_process_works_date ON public.process_of_works USING btree (date) TABLESPACE pg_default;

-- Sample INSERT
INSERT INTO public.process_of_works (vehicle_id, registration_no, date, time, nature_of_work, rectified_results, bill_no, amount)
VALUES ('V001', 'TN01AB1234', '2024-01-15', '14:30:00', 'Engine oil change', 'Oil changed successfully', 'BILL001', '₹1500');
