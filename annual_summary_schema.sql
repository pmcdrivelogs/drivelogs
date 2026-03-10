-- Annual Summary & Recommendations Schema
-- This system has TWO separate tables for the two sections

-- TABLE 1: Annual Summary (Complaints Received)
CREATE TABLE IF NOT EXISTS public.annual_summary_complaints (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    registration_no TEXT NOT NULL,
    from_year TEXT NOT NULL,
    to_year TEXT NOT NULL,
    date DATE,
    complaint TEXT,
    action_taken TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TABLE 2: Annual Recommendations (Next Year)
CREATE TABLE IF NOT EXISTS public.annual_summary_recommendations (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    registration_no TEXT NOT NULL,
    recommendation_year TEXT NOT NULL,
    approx_date DATE,
    anticipated_complaint TEXT,
    prevention TEXT,
    remarks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_annual_summary_complaints_vehicle_id ON public.annual_summary_complaints(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_annual_summary_complaints_from_year ON public.annual_summary_complaints(from_year);

CREATE INDEX IF NOT EXISTS idx_annual_summary_recommendations_vehicle_id ON public.annual_summary_recommendations(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_annual_summary_recommendations_year ON public.annual_summary_recommendations(recommendation_year);

-- Sample insert statements
INSERT INTO public.annual_summary_complaints (
    vehicle_id, registration_no, from_year, to_year,
    date, complaint, action_taken, status
) VALUES (
    'V001', 'TN01AB1234', '2024', '2025',
    '2024-06-15', 'Engine overheating issue', 'Radiator replaced and coolant refilled', 'Processed - Issue resolved'
);

INSERT INTO public.annual_summary_recommendations (
    vehicle_id, registration_no, recommendation_year,
    approx_date, anticipated_complaint, prevention, remarks
) VALUES (
    'V001', 'TN01AB1234', '2025',
    '2025-04-15', 'Brake pad wear expected', 'Schedule brake inspection and replacement', 'Monitor every 3 months'
);
