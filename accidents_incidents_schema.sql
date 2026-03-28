-- Accidents / Incidents Module Schema

CREATE TABLE accidents_incidents (
  id SERIAL PRIMARY KEY,

  -- Auto fields
  entry_no         TEXT NOT NULL,
  date_time        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- Vehicle / Driver identifiers
  vehicle_id       TEXT,
  registration_no  TEXT,
  driver_id        TEXT,
  driver_name      TEXT,

  -- Incident details
  place_of_incident         TEXT,   -- ONROAD / IN CAMPUS / PARKING / OTHERS
  place_description         TEXT,   -- filled when OTHERS

  type_of_incident          TEXT,   -- ON ROAD ACCIDENT / DRIVER NEGLIGENCE / ANONYMOUS BRAKE THROUGH / OTHERS
  type_of_incident_desc     TEXT,   -- filled when OTHERS

  type_of_loss              TEXT,   -- FATAL / FRACTURES / MINOR WOUNDS / MAJOR VEHICLE DAMAGE / MINOR VEHICLE DAMAGE / OTHERS
  type_of_loss_desc         TEXT,   -- filled when OTHERS

  case_description          TEXT,

  -- Hospitalisation
  hospitalized              TEXT DEFAULT 'NO',  -- YES / NO
  hospital_name             TEXT,
  type_of_treatment         TEXT,
  treatment_expenditure     NUMERIC(12,2),

  -- Police case
  case_filed_police         TEXT DEFAULT 'NO',  -- YES / NO
  fir_csr_no                TEXT,
  police_date               DATE,
  police_status             TEXT,
  police_closed_date        DATE,

  -- Settlement
  settled_in_person         TEXT DEFAULT 'NO',  -- YES / NO
  minutes_of_settlement     TEXT,
  settlement_status         TEXT DEFAULT 'PENDING',  -- PENDING / CLOSED
  settlement_closed_date    DATE,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settlement persons (multiple rows per incident)
CREATE TABLE accidents_incidents_settlement_persons (
  id          SERIAL PRIMARY KEY,
  incident_id INTEGER NOT NULL REFERENCES accidents_incidents(id) ON DELETE CASCADE,
  person_name TEXT NOT NULL
);

CREATE INDEX idx_ai_vehicle_id   ON accidents_incidents(vehicle_id);
CREATE INDEX idx_ai_driver_id    ON accidents_incidents(driver_id);
CREATE INDEX idx_ai_date_time    ON accidents_incidents(date_time);
CREATE INDEX idx_ai_entry_no     ON accidents_incidents(entry_no);
