-- ALTER TABLE to add new vehicle fields
-- Run these commands to extend the vehicles table with comprehensive vehicle information

ALTER TABLE public.vehicles
ADD COLUMN date_of_registration DATE NULL,
ADD COLUMN chassis_number TEXT NULL,
ADD COLUMN engine_number TEXT NULL,
ADD COLUMN fuel_type TEXT NULL,
ADD COLUMN emission_norms TEXT NULL,
ADD COLUMN vehicle_class TEXT NULL,
ADD COLUMN make TEXT NULL,
ADD COLUMN model TEXT NULL,
ADD COLUMN color TEXT NULL,
ADD COLUMN body_type TEXT NULL,
ADD COLUMN seating_capacity INTEGER NULL,
ADD COLUMN unladen_weight TEXT NULL,
ADD COLUMN laden_weight TEXT NULL,
ADD COLUMN horse_power TEXT NULL,
ADD COLUMN cubic_capacity TEXT NULL,
ADD COLUMN financier TEXT NULL,
ADD COLUMN number_of_axles INTEGER NULL,
ADD COLUMN no_of_cylinders INTEGER NULL,
ADD COLUMN month_year_manufacturing TEXT NULL,
ADD COLUMN fitness_validity DATE NULL,
ADD COLUMN insurance_validity DATE NULL,
ADD COLUMN insurance_company TEXT NULL,
ADD COLUMN permit_validity DATE NULL,
ADD COLUMN permit_district TEXT NULL,
ADD COLUMN pucc_validity DATE NULL,
ADD COLUMN tax_validity DATE NULL;

-- Display the updated table structure
SELECT * FROM public.vehicles LIMIT 1;
