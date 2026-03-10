-- Incidents & Reports Schema
-- Two separate tables for incidents and claims

-- Table 1: Incidents
CREATE TABLE incidents_reports_incidents (
  id SERIAL PRIMARY KEY,
  vehicle_id TEXT NOT NULL,
  registration_no TEXT NOT NULL,
  from_year TEXT NOT NULL,
  to_year TEXT NOT NULL,
  date DATE,
  nature_of_incident TEXT,
  reasons_causes TEXT,
  responsible TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_incidents_vehicle_id ON incidents_reports_incidents(vehicle_id);
CREATE INDEX idx_incidents_year ON incidents_reports_incidents(from_year, to_year);

-- Table 2: Claimssss
CREATE TABLE incidents_reports_claims (
  id SERIAL PRIMARY KEY,
  vehicle_id TEXT NOT NULL,
  registration_no TEXT NOT NULL,
  from_year TEXT NOT NULL,
  to_year TEXT NOT NULL,
  approx_date DATE,
  nature_of_claim TEXT,
  mode_of_claim TEXT,
  claim_value_responsible TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_claims_vehicle_id ON incidents_reports_claims(vehicle_id);
CREATE INDEX idx_claims_year ON incidents_reports_claims(from_year, to_year);

-- Sample data for testing
INSERT INTO incidents_reports_incidents (vehicle_id, registration_no, from_year, to_year, date, nature_of_incident, reasons_causes, responsible) VALUES
('V001', 'TN01AB1234', '2024', '2025', '2024-07-15', 'Minor collision at parking area', 'Poor visibility due to heavy rain', 'Driver - John Doe'),
('V001', 'TN01AB1234', '2024', '2025', '2024-11-20', 'Tire burst on highway', 'Worn out tire not replaced on time', 'Maintenance team oversight');

INSERT INTO incidents_reports_claims (vehicle_id, registration_no, from_year, to_year, approx_date, nature_of_claim, mode_of_claim, claim_value_responsible) VALUES
('V001', 'TN01AB1234', '2024', '2025', '2024-07-20', 'Insurance claim for collision damage', 'Insurance settlement', 'Rs. 25,000 - Insurance Company'),
('V001', 'TN01AB1234', '2024', '2025', '2024-11-25', 'Institutional claim for tire replacement', 'Personal settlement', 'Rs. 8,000 - Institution budget');
