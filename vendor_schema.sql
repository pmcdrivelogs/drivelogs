-- Vendor Management Table Schema
CREATE TABLE IF NOT EXISTS vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id VARCHAR(50) UNIQUE NOT NULL,
    ref_number VARCHAR(50) DEFAULT 'PMCTECH/LOGI/FORM 2/001',
    
    -- Organization Details
    organization_name VARCHAR(255) NOT NULL,
    organization_type VARCHAR(100),
    contact_number VARCHAR(20),
    email_id VARCHAR(255),
    website VARCHAR(255),
    
    -- Address Information
    address TEXT,
    phone_number VARCHAR(20),
    
    -- Purchase Details
    type_of_purchase VARCHAR(100),
    date_of_vendorship DATE,
    description TEXT,
    
    -- Approval & Status
    approval_status VARCHAR(50) DEFAULT 'pending' CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    approved_by VARCHAR(255),
    approved_date TIMESTAMP,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    
    -- Metadata
    notes TEXT,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'blacklisted'))
);

-- Function to auto-generate Vendor ID
CREATE OR REPLACE FUNCTION get_next_vendor_id()
RETURNS VARCHAR AS $$
DECLARE
    next_id INTEGER;
    new_vendor_id VARCHAR(50);
BEGIN
    -- Get the highest existing vendor number
    SELECT COALESCE(
        MAX(CAST(SUBSTRING(vendor_id FROM 'VEN(\d+)') AS INTEGER)),
        0
    ) INTO next_id
    FROM vendors
    WHERE vendor_id ~ 'VEN\d+';
    
    -- Increment and format (using hyphens instead of slashes for URL compatibility)
    next_id := next_id + 1;
    new_vendor_id := 'PMC-LOGI-VEN' || LPAD(next_id::TEXT, 3, '0');
    
    RETURN new_vendor_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-generate vendor_id if not provided
CREATE OR REPLACE FUNCTION set_vendor_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.vendor_id IS NULL OR NEW.vendor_id = '' THEN
        NEW.vendor_id := get_next_vendor_id();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_vendor_id
BEFORE INSERT ON vendors
FOR EACH ROW
EXECUTE FUNCTION set_vendor_id();

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_vendor_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_vendor_timestamp
BEFORE UPDATE ON vendors
FOR EACH ROW
EXECUTE FUNCTION update_vendor_timestamp();

-- Create indexes for better performance
CREATE INDEX idx_vendors_vendor_id ON vendors(vendor_id);
CREATE INDEX idx_vendors_organization_name ON vendors(organization_name);
CREATE INDEX idx_vendors_status ON vendors(status);
CREATE INDEX idx_vendors_approval_status ON vendors(approval_status);
CREATE INDEX idx_vendors_created_at ON vendors(created_at);

-- Sample organization types
COMMENT ON COLUMN vendors.organization_type IS 'Types: Government, Private Limited, Public Limited, Partnership, Proprietorship, NGO, Trust, etc.';

-- Sample purchase types
COMMENT ON COLUMN vendors.type_of_purchase IS 'Types: Raw Materials, Equipment, Services, Maintenance, Consumables, Software, etc.';

-- Enable Row Level Security (optional)
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;

-- Create policy for authenticated users
CREATE POLICY vendors_policy ON vendors
    FOR ALL
    USING (true)
    WITH CHECK (true);
