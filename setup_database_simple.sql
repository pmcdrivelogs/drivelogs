-- ============================================
-- Drive Logs - Simple Database Setup (Plain Text Passwords)
-- WARNING: This is NOT secure for production!
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. USERS TABLE (Regular Users)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    phone TEXT,
    department TEXT,
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
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
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
    user_identifier TEXT NOT NULL,
    user_type TEXT,
    success BOOLEAN NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_login_logs_timestamp ON login_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_login_logs_identifier ON login_logs(user_identifier);

-- ============================================
-- 4. INSERT SAMPLE DATA
-- ============================================

-- Sample User
INSERT INTO users (email, password, full_name, role, phone, department)
VALUES (
    'test@example.com',
    'password123',
    'Test User',
    'user',
    '+1234567890',
    'Transport'
) ON CONFLICT (email) DO NOTHING;

-- Sample Super Admin
INSERT INTO super_admins (username, password, full_name, email, phone)
VALUES (
    'admin',
    'admin123',
    'Super Administrator',
    'admin@drivelogs.com',
    '+1234567890'
) ON CONFLICT (username) DO NOTHING;

-- ============================================
-- 5. TRIGGERS FOR UPDATED_AT
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
-- Sample Data to Add More Users/Admins
-- ============================================

-- To add a new user, run:
-- INSERT INTO users (email, password, full_name, role, department)
-- VALUES ('user@example.com', 'yourpassword', 'User Name', 'user', 'Department Name');

-- To add a new admin, run:
-- INSERT INTO super_admins (username, password, full_name, email)
-- VALUES ('adminuser', 'yourpassword', 'Admin Name', 'admin@example.com');
