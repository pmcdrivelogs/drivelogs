-- ALTER: Add financial columns to accidents_incidents
-- Run this once in your Supabase SQL editor

ALTER TABLE accidents_incidents
  ADD COLUMN IF NOT EXISTS police_total_paid   NUMERIC(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS settlement_amount   NUMERIC(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_loss          NUMERIC(12,2) DEFAULT 0;

-- total_loss = treatment_expenditure + police_total_paid + settlement_amount
-- It is stored (not computed) so it persists even if sub-values change.
