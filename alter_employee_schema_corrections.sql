-- =====================================================
-- EMPLOYEE SCHEMA CORRECTIONS - ALTER TABLE STATEMENTS
-- =====================================================

-- 1. RENAME COLUMNS
ALTER TABLE public.employees RENAME COLUMN id_no TO dl_no;
ALTER TABLE public.employees RENAME COLUMN lmv_ref TO lmv_date_of_issue;
ALTER TABLE public.employees RENAME COLUMN hpv_ref TO hmv_date_of_issue;
ALTER TABLE public.employees RENAME COLUMN validity_lmv TO validity_nt;
ALTER TABLE public.employees RENAME COLUMN validity_hpv TO validity_tr;
ALTER TABLE public.employees RENAME COLUMN rto_dept TO rto_ref;
ALTER TABLE public.employees RENAME COLUMN max_tongue TO max_education;

-- 2. CHANGE DATA TYPES (LMV and HMV refs to date fields)
ALTER TABLE public.employees ALTER COLUMN lmv_date_of_issue TYPE date USING lmv_date_of_issue::date;
ALTER TABLE public.employees ALTER COLUMN hmv_date_of_issue TYPE date USING hmv_date_of_issue::date;

-- 3. ADD NEW AWARDS & APPRECIATION JSONB FIELD
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS awards JSONB DEFAULT '[]'::jsonb;
COMMENT ON COLUMN public.employees.awards IS 'Awards and appreciation records: [{date, nature, remarks}]';

-- NOTE: Accidents JSONB structure should include status field: [{date, description (not describing), type, case_no, status}]
-- The status field is for manual entry to track accident status

-- 4. HEALTH SECTION - REMOVE FROM/TO DATES, ADD SINGLE CHECKUP DATE
-- Drop old columns
ALTER TABLE public.employees DROP COLUMN IF EXISTS vision_checkup_from;
ALTER TABLE public.employees DROP COLUMN IF EXISTS vision_checkup_to;
ALTER TABLE public.employees DROP COLUMN IF EXISTS hearing_checkup_from;
ALTER TABLE public.employees DROP COLUMN IF EXISTS hearing_checkup_to;
ALTER TABLE public.employees DROP COLUMN IF EXISTS bp_checkup_from;
ALTER TABLE public.employees DROP COLUMN IF EXISTS bp_checkup_to;
ALTER TABLE public.employees DROP COLUMN IF EXISTS sugar_checkup_from;
ALTER TABLE public.employees DROP COLUMN IF EXISTS sugar_checkup_to;
ALTER TABLE public.employees DROP COLUMN IF EXISTS fractures_checkup_from;
ALTER TABLE public.employees DROP COLUMN IF EXISTS fractures_checkup_to;

-- Add new single checkup date columns
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS vision_checkup_date date NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS hearing_checkup_date date NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS bp_checkup_date date NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS sugar_checkup_date date NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS fractures_checkup_date date NULL;

-- 5. PERSONAL DATA - ADD AGE FIELDS
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS father_age integer NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS mother_age integer NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS spouse_age integer NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS child1_age integer NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS child2_age integer NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS child3_age integer NULL;

-- 6. REMOVE PREVIOUS EMPLOYEE NUMBER FIELDS
ALTER TABLE public.employees DROP COLUMN IF EXISTS previous_emp_no;
ALTER TABLE public.employees DROP COLUMN IF EXISTS previous_emp_no2;

-- 7. ADD NOMINEE FIELDS
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS nominee_name character varying(255) NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS nominee_phone_no character varying(20) NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS nominee_relation character varying(100) NULL;

-- 8. ADD EXPECTED DATE OF JOINING, EXPECTED SALARY, AGE, AND RENAME EXPECTED TO REFERENCE
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS expected_date_of_joining date NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS expected_salary character varying(100) NULL;
ALTER TABLE public.employees ADD COLUMN IF NOT EXISTS age integer NULL;
ALTER TABLE public.employees RENAME COLUMN expected TO reference;

-- 9. ADD COMMENTS FOR NEW FIELDS
COMMENT ON COLUMN public.employees.dl_no IS 'Driving Licence Number';
COMMENT ON COLUMN public.employees.lmv_date_of_issue IS 'LMV Date of Issue';
COMMENT ON COLUMN public.employees.hmv_date_of_issue IS 'HMV Date of Issue (formerly HPV)';
COMMENT ON COLUMN public.employees.validity_nt IS 'Validity NT (formerly LMV)';
COMMENT ON COLUMN public.employees.validity_tr IS 'Validity TR (formerly HPV)';
COMMENT ON COLUMN public.employees.rto_ref IS 'RTO Reference';
COMMENT ON COLUMN public.employees.max_education IS 'Maximum Education level';
COMMENT ON COLUMN public.employees.nominee_name IS 'Emergency contact nominee name';
COMMENT ON COLUMN public.employees.nominee_phone_no IS 'Nominee phone number';
COMMENT ON COLUMN public.employees.nominee_relation IS 'Nominee relation to employee';
COMMENT ON COLUMN public.employees.expected_date_of_joining IS 'Expected date of joining';
COMMENT ON COLUMN public.employees.expected_salary IS 'Expected salary';
COMMENT ON COLUMN public.employees.age IS 'Employee age';
COMMENT ON COLUMN public.employees.reference IS 'Reference (formerly expected)';

-- 10. UPDATE EXPERIENCE JSONB STRUCTURE (if needed for existing data)
-- Note: This will update existing records' experience structure from {years, ...} to {from_date, to_date, ...}
-- Only run if you have existing data that needs migration
-- UPDATE public.employees 
-- SET experience = (
--   SELECT jsonb_agg(
--     jsonb_build_object(
--       'from_date', NULL,
--       'to_date', NULL,
--       'designation', elem->>'designation',
--       'organization', elem->>'organization',
--       'vehicle_type', elem->>'vehicle_type'
--     )
--   )
--   FROM jsonb_array_elements(experience) AS elem
-- )
-- WHERE experience IS NOT NULL AND experience != '[]'::jsonb;

-- =====================================================
-- END OF ALTER TABLE STATEMENTS
-- =====================================================
