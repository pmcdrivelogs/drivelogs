-- =====================================================
-- EMPLOYEE TABLE SCHEMA FOR SUPABASE
-- =====================================================
-- Table: employees
-- Description: Stores complete employee/driver profile information
-- Reference: PMCTECH Employee Profile Form
-- =====================================================

CREATE TABLE IF NOT EXISTS employees (
    -- Primary Key
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- Auto-generated Employee ID
    employee_id VARCHAR(50) NOT NULL UNIQUE,
    
    -- Basic Profile
    name VARCHAR(255) NOT NULL,
    id_no VARCHAR(100),
    date_of_birth DATE,
    date_of_issue DATE,
    badge_no VARCHAR(100),
    lmv_ref VARCHAR(100),
    rto_dept VARCHAR(100),
    hpv_ref VARCHAR(100),
    validity_lmv DATE,
    validity_hpv DATE,
    aadhar_no VARCHAR(20),
    nativity VARCHAR(100),
    
    -- Experience (JSON array)
    experience JSONB DEFAULT '[]',
    
    -- Accidents/Incidents (JSON array)
    accidents JSONB DEFAULT '[]',
    
    -- Health & Fitness
    vision VARCHAR(50),
    vision_checkup_from DATE,
    vision_checkup_to DATE,
    hearing VARCHAR(50),
    hearing_checkup_from DATE,
    hearing_checkup_to DATE,
    bp VARCHAR(50),
    bp_checkup_from DATE,
    bp_checkup_to DATE,
    sugar VARCHAR(50),
    sugar_checkup_from DATE,
    sugar_checkup_to DATE,
    fractures VARCHAR(50),
    fractures_checkup_from DATE,
    fractures_checkup_to DATE,
    
    -- Habits/Practices
    alcohol VARCHAR(50),
    gutkha VARCHAR(50),
    smoking VARCHAR(50),
    gambling VARCHAR(50),
    tobacco VARCHAR(50),
    other_habits VARCHAR(255),
    
    -- Personal Data
    father_name VARCHAR(255),
    father_occupation VARCHAR(255),
    mother_name VARCHAR(255),
    mother_occupation VARCHAR(255),
    spouse_name VARCHAR(255),
    spouse_occupation VARCHAR(255),
    child1_name VARCHAR(255),
    child1_occupation VARCHAR(255),
    child2_name VARCHAR(255),
    child2_occupation VARCHAR(255),
    child3_name VARCHAR(255),
    child3_occupation VARCHAR(255),
    max_tongue VARCHAR(255),
    school VARCHAR(255),
    mother_tongue VARCHAR(100),
    other_lang VARCHAR(255),
    previous_emp_no VARCHAR(100),
    previous_emp_no2 VARCHAR(100),
    nationality VARCHAR(100),
    community_caste VARCHAR(100),
    religion VARCHAR(100),
    permanent_address TEXT,
    present_address TEXT,
    phone_no VARCHAR(20),
    whatsapp_phone_no VARCHAR(20),
    number_phone_no VARCHAR(20),
    
    -- Driving & Eligibility
    driving_nature VARCHAR(100),
    route TEXT,
    expected TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    created_by VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'terminated'))
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_employees_employee_id ON employees(employee_id);
CREATE INDEX IF NOT EXISTS idx_employees_name ON employees(name);
CREATE INDEX IF NOT EXISTS idx_employees_aadhar ON employees(aadhar_no);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employees_created_at ON employees(created_at);

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_employees_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_employees_updated_at
    BEFORE UPDATE ON employees
    FOR EACH ROW
    EXECUTE FUNCTION update_employees_updated_at();

-- Function to get next employee ID
CREATE OR REPLACE FUNCTION get_next_employee_id()
RETURNS TEXT AS $$
DECLARE
    next_num INTEGER;
    next_employee_id TEXT;
BEGIN
    SELECT COALESCE(MAX(CAST(SUBSTRING(employee_id FROM 'EMP([0-9]+)') AS INTEGER)), 1000) + 1
    INTO next_num
    FROM employees;
    
    next_employee_id := 'EMP' || LPAD(next_num::TEXT, 5, '0');
    RETURN next_employee_id;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

ALTER TABLE employees ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all access to employees" ON employees;

CREATE POLICY "Allow all access to employees"
    ON employees
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- =====================================================
-- GRANTS
-- =====================================================

GRANT ALL ON employees TO authenticated;
GRANT ALL ON employees TO anon;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE employees IS 'Stores complete employee/driver profile information';
COMMENT ON COLUMN employees.employee_id IS 'Auto-generated unique employee ID (EMP00001, EMP00002, etc.)';
COMMENT ON COLUMN employees.experience IS 'JSON array of work experience records';
COMMENT ON COLUMN employees.accidents IS 'JSON array of accident/incident records';
COMMENT ON COLUMN employees.status IS 'Employee status: active, inactive, or terminated';
