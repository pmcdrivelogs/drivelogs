-- Stock Issue Register Table Schema for Supabase

CREATE TABLE IF NOT EXISTS stock_issue_register (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    entry_no TEXT NOT NULL,
    purchase_id UUID REFERENCES purchases(id),
    
    -- Part Details
    part_no TEXT,
    part_name TEXT,
    
    -- Vehicle Details
    vehicle_no TEXT,
    vehicle_id TEXT,
    
    -- Issue Details
    date DATE NOT NULL,
    time TIME NOT NULL,
    kilometer NUMERIC(10, 2),
    
    -- Responsibility Details
    issuing_person_name TEXT NOT NULL,
    driver_responsible TEXT,
    mechanic_responsible TEXT,
    
    -- Additional Info
    comments TEXT,
    status TEXT DEFAULT 'issued',
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_stock_issue_entry_no ON stock_issue_register(entry_no);
CREATE INDEX IF NOT EXISTS idx_stock_issue_purchase_id ON stock_issue_register(purchase_id);
CREATE INDEX IF NOT EXISTS idx_stock_issue_date ON stock_issue_register(date);
CREATE INDEX IF NOT EXISTS idx_stock_issue_vehicle_no ON stock_issue_register(vehicle_no);
CREATE INDEX IF NOT EXISTS idx_stock_issue_created_at ON stock_issue_register(created_at);

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_stock_issue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_stock_issue_updated_at
    BEFORE UPDATE ON stock_issue_register
    FOR EACH ROW
    EXECUTE FUNCTION update_stock_issue_updated_at();

-- Function to get next entry number
CREATE OR REPLACE FUNCTION get_next_stock_issue_entry_no()
RETURNS TEXT AS $$
DECLARE
    next_num INTEGER;
    next_entry_no TEXT;
BEGIN
    SELECT COALESCE(MAX(CAST(SUBSTRING(entry_no FROM '[0-9]+') AS INTEGER)), 0) + 1
    INTO next_num
    FROM stock_issue_register;
    
    next_entry_no := LPAD(next_num::TEXT, 3, '0');
    RETURN next_entry_no;
END;
$$ LANGUAGE plpgsql;

-- Enable Row Level Security (RLS)
ALTER TABLE stock_issue_register ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Allow authenticated users to read stock issue records" ON stock_issue_register;
DROP POLICY IF EXISTS "Allow authenticated users to insert stock issue records" ON stock_issue_register;
DROP POLICY IF EXISTS "Allow authenticated users to update stock issue records" ON stock_issue_register;
DROP POLICY IF EXISTS "Allow all access to stock issue records" ON stock_issue_register;

-- Create policy to allow all operations (for service role and authenticated users)
CREATE POLICY "Allow all access to stock issue records"
    ON stock_issue_register
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Grant permissions
GRANT ALL ON stock_issue_register TO authenticated;
GRANT ALL ON stock_issue_register TO anon;
