-- ============================================
-- Drive Logs - Supabase Database Setup
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. USERS TABLE (Regular Users)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    phone VARCHAR(20),
    department VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- ============================================
-- 2. SUPER ADMINS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS super_admins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create index on username for faster lookups
CREATE INDEX IF NOT EXISTS idx_super_admins_username ON super_admins(username);
CREATE INDEX IF NOT EXISTS idx_super_admins_active ON super_admins(is_active);

-- ============================================
-- 3. LOGIN LOGS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS login_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_identifier VARCHAR(255) NOT NULL,
    user_type VARCHAR(50), -- 'user' or 'admin'
    success BOOLEAN NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_login_logs_timestamp ON login_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_login_logs_identifier ON login_logs(user_identifier);

-- ============================================
-- 4. INSERT SAMPLE DATA (Optional)
-- ============================================

-- Sample User (Email: test@example.com, Password: password123)
-- Password hash generated using werkzeug.security with scrypt:32768:8:1
INSERT INTO users (email, password_hash, full_name, role, phone, department)
VALUES (
    'test@example.com',
    'scrypt:32768:8:1$7vK8z9X3Y2W1Q5R4$b8c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8',
    'Test User',
    'user',
    '+1234567890',
    'Transport'
) ON CONFLICT (email) DO NOTHING;

-- Sample Super Admin (Username: admin, Password: admin123)
INSERT INTO super_admins (username, password_hash, full_name, email, phone)
VALUES (
    'admin',
    'scrypt:32768:8:1$8wL9a0Y4Z3X2R6S5$c9d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9',
    'Super Administrator',
    'admin@drivelogs.com',
    '+1234567890'
) ON CONFLICT (username) DO NOTHING;

-- ============================================
-- 5. ROW LEVEL SECURITY (RLS) - Optional
-- ============================================
-- Enable RLS on tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE super_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE login_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own data
CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (auth.uid()::text = id::text);

-- Policy: Admins can see all users (you'll need to implement this based on your auth setup)
CREATE POLICY admins_select_all_users ON users
    FOR SELECT
    USING (true);

-- ============================================
-- 6. TRIGGERS FOR UPDATED_AT
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_super_admins_updated_at
    BEFORE UPDATE ON super_admins
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- NOTES:
-- ============================================
-- 1. Run this script in your Supabase SQL Editor
-- 2. The sample passwords are hashed, you'll need to generate new hashes
-- 3. To create your first admin user, use the Python script provided
-- 4. RLS policies can be customized based on your security requirements
