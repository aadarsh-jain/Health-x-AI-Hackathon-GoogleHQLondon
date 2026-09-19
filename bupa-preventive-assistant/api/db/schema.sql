-- =====================================================================
-- Bupa Preventive Health Assistant — SCHEMA (spec §8)
-- Target: Cloud SQL (Postgres 14+) / AlloyDB. Run BEFORE seed.sql.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- for gen_random_uuid()

-- users
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  user_type TEXT CHECK (user_type IN ('new','existing')) NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);

-- preventive_services (PUBLIC catalog — the services we help people discover)
CREATE TABLE IF NOT EXISTS preventive_services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_family TEXT,          -- health_assessment | genomic_health | digital_gp | health_programme | mental_health
  name TEXT,
  description TEXT,
  eligibility_rule JSONB,
  typical_cadence_months INT
);

-- pre_survey_responses (New User path). Section 1 core = MANDATORY.
CREATE TABLE IF NOT EXISTS pre_survey_responses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  age INT NOT NULL,
  height_cm NUMERIC NOT NULL,
  weight_kg NUMERIC NOT NULL,
  blood_type TEXT NOT NULL,
  ethnicity TEXT,
  bmi NUMERIC,
  family_history JSONB,
  lifestyle JSONB,
  medications_allergies JSONB,
  symptoms JSONB,
  wellbeing_flags JSONB,
  report_id UUID,
  submitted_at TIMESTAMP DEFAULT now()
);

-- uploaded_reports (section 4.5 — the "resume upload" path)
CREATE TABLE IF NOT EXISTS uploaded_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  source TEXT CHECK (source IN ('upload','bupa_records','manual')) NOT NULL,
  file_uri TEXT,
  extraction_status TEXT DEFAULT 'pending',   -- pending, parsed, failed
  extracted_json JSONB,
  uploaded_at TIMESTAMP DEFAULT now()
);

-- clinical_signals (MedGemma raw output — NEVER shown to the user directly)
CREATE TABLE IF NOT EXISTS clinical_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  report_id UUID REFERENCES uploaded_reports(id),
  signal_type TEXT,
  value JSONB,
  confidence FLOAT,
  passed_guardrail BOOLEAN DEFAULT false,
  extracted_at TIMESTAMP DEFAULT now()
);

-- recommendations (guardrail-approved, transparent — spec §5.2)
CREATE TABLE IF NOT EXISTS recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  signal_id UUID REFERENCES clinical_signals(id),
  service TEXT NOT NULL,
  reason TEXT NOT NULL,
  trigger_data JSONB NOT NULL,
  next_step TEXT NOT NULL,
  status TEXT DEFAULT 'shown',   -- shown, actioned, dismissed
  created_at TIMESTAMP DEFAULT now()
);

-- policies (context, not the product)
CREATE TABLE IF NOT EXISTS policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  policy_type TEXT,
  status TEXT,
  coverage_summary TEXT,
  includes_services JSONB,
  renewal_date DATE
);

-- claims
CREATE TABLE IF NOT EXISTS claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  policy_id UUID REFERENCES policies(id),
  claim_type TEXT,
  filed_at TIMESTAMP,
  status TEXT
);

-- health_events (seeded/self-reported/MedGemma-derived)
CREATE TABLE IF NOT EXISTS health_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  event_type TEXT,
  event_date DATE,
  result_summary TEXT,
  risk_flags JSONB,
  source TEXT,
  notes TEXT
);

-- notifications (Trigger/Action output, polled by Chat UI)
CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  type TEXT,
  service_family TEXT,
  message TEXT,
  triggered_at TIMESTAMP DEFAULT now(),
  read BOOLEAN DEFAULT false
);

-- interaction_log (for BigQuery export / analytics)
CREATE TABLE IF NOT EXISTS interaction_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  ip_code TEXT,
  op_code TEXT,
  mechanism TEXT,
  service_recommended TEXT,
  logged_at TIMESTAMP DEFAULT now()
);

-- Helpful indexes for the demo queries
CREATE INDEX IF NOT EXISTS idx_reco_user       ON recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_notif_user       ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_user     ON clinical_signals(user_id);
CREATE INDEX IF NOT EXISTS idx_health_user      ON health_events(user_id);
CREATE INDEX IF NOT EXISTS idx_policies_user    ON policies(user_id);
CREATE INDEX IF NOT EXISTS idx_ilog_user        ON interaction_log(user_id);
