-- =====================================================================
-- Bupa Preventive Health Assistant — SEED DATA
-- Target: Cloud SQL (Postgres) / AlloyDB. Run AFTER schema.sql (spec §8).
-- Reference date for the demo: 2026-09-18 (see spec currentDate).
--
-- Design goals for this seed (maps to spec §3.5 gap types + §15 demo):
--   u1  NEW,  uploaded report, 52M, family-history diabetes
--             -> HERO demo: assessment-overdue + genomic gap
--   u5  NEW,  manual entry,    70F, senior -> Senior Mode + assessment discovery
--   u2  EXISTING, 68           -> assessment overdue (18 mo) + renewal nudge
--   u3  EXISTING, 34           -> lifestyle-risk programme + early mental-health signal
--   u4  EXISTING, 45           -> redundant/non-recommended policy alert
--
-- All member data below is FAKE. Only the preventive_services catalog text
-- reflects Bupa's PUBLIC service descriptions (spec §3.6 / data-ethics note).
-- Fixed UUIDs are used so foreign keys stay readable.
-- =====================================================================

BEGIN;

-- Optional: make this script idempotent when re-run during the hackathon.
TRUNCATE interaction_log, notifications, recommendations, clinical_signals,
         health_events, claims, policies, uploaded_reports,
         pre_survey_responses, preventive_services, users RESTART IDENTITY CASCADE;

-- ---------------------------------------------------------------------
-- 1. USERS
-- ---------------------------------------------------------------------
INSERT INTO users (id, email, user_type, created_at) VALUES
  ('11111111-1111-1111-1111-111111111111', 'ravi.new@example.com',      'new',      '2026-09-18 09:00:00'),
  ('22222222-2222-2222-2222-222222222222', 'margaret.senior@example.com','existing', '2021-02-11 10:30:00'),
  ('33333333-3333-3333-3333-333333333333', 'sam.busy@example.com',      'existing', '2023-06-01 08:15:00'),
  ('44444444-4444-4444-4444-444444444444', 'priya.multi@example.com',   'existing', '2022-11-20 14:45:00'),
  ('55555555-5555-5555-5555-555555555555', 'joan.new@example.com',      'new',      '2026-09-18 09:05:00');

-- ---------------------------------------------------------------------
-- 2. PREVENTIVE_SERVICES CATALOG (public Bupa offerings — the 5 families)
--    eligibility_rule is machine-readable for the Recommendation Engine.
-- ---------------------------------------------------------------------
INSERT INTO preventive_services (id, service_family, name, description, eligibility_rule, typical_cadence_months) VALUES
  ('aaaa0001-0000-0000-0000-000000000001', 'health_assessment', 'Bupa Health Assessment',
   'A structured health MOT covering blood tests, biometrics (blood pressure, cholesterol, BMI) and a lifestyle review, with a personalised report and next steps.',
   '{"min_age": 40, "months_since_last_assessment_gte": 12, "any_risk_flag": true}', 18),

  ('aaaa0002-0000-0000-0000-000000000002', 'genomic_health', 'Bupa Genomic Health / Blueprint',
   'A DNA-based screening programme that assesses inherited risk for common conditions and builds a personalised prevention plan.',
   '{"family_history_any": ["heart_disease","type2_diabetes","cancer","stroke"], "proactive_interest": true}', 0),

  ('aaaa0003-0000-0000-0000-000000000003', 'digital_gp', 'Bupa Digital GP',
   'On-demand video or phone GP appointments, including advice, referrals and prescriptions where appropriate.',
   '{"has_symptom": true, "convenience_need": true}', 0),

  ('aaaa0004-0000-0000-0000-000000000004', 'health_programme', 'Bupa Personalised Health Programme',
   'Ongoing coaching for weight, fitness, nutrition and chronic-risk reduction, tailored to your goals and lifestyle.',
   '{"any_lifestyle_flag": ["sedentary","high_bmi","smoker","poor_diet"]}', 0),

  ('aaaa0005-0000-0000-0000-000000000005', 'mental_health', 'Bupa Early Mental Health Support',
   'Direct-access mental-health assessment and talking therapies, without needing a GP referral first.',
   '{"any_wellbeing_flag": ["high_stress","poor_sleep","low_mood"], "screener_threshold_met": true}', 0);

-- ---------------------------------------------------------------------
-- 3. UPLOADED_REPORTS (section 4.5 "resume upload" path)
--    r1: u1 uploaded a PDF -> MedGemma parsed it into extracted_json (pre-fill payload)
-- ---------------------------------------------------------------------
INSERT INTO uploaded_reports (id, user_id, source, file_uri, extraction_status, extracted_json, uploaded_at) VALUES
  ('da7a0001-0000-0000-0000-000000000001',
   '11111111-1111-1111-1111-111111111111',
   'upload',
   'gs://bupa-demo-uploads/u1/health_report_2026.pdf',
   'parsed',
   '{
      "age": 52, "height_cm": 178, "weight_kg": 91, "blood_type": "O+",
      "family_history": {"conditions": ["type2_diabetes"], "notes": "father diagnosed at 58"},
      "lifestyle": {"tobacco": "former", "alcohol": "2-4_month", "activity_days": "1-2"},
      "medications_allergies": {"medications": [{"name": "None", "dose": "", "freq": ""}]},
      "fields_not_found": ["stress_level", "sleep_hours"]
    }',
   '2026-09-18 09:01:30');

-- ---------------------------------------------------------------------
-- 4. PRE_SURVEY_RESPONSES (NEW users only). Section 1 = mandatory.
--    u1: confirmed/edited from the uploaded report (report_id set)
--    u5: entered manually, senior (age 70 -> Senior Mode auto-offer)
-- ---------------------------------------------------------------------
INSERT INTO pre_survey_responses
  (id, user_id, age, height_cm, weight_kg, blood_type, ethnicity, bmi,
   family_history, lifestyle, medications_allergies, symptoms, wellbeing_flags,
   report_id, submitted_at) VALUES
  ('bbbb0001-0000-0000-0000-000000000001',
   '11111111-1111-1111-1111-111111111111',
   52, 178, 91, 'O+', 'asian', 28.7,
   '{"conditions": ["type2_diabetes"], "notes": "father diagnosed at 58"}',
   '{"activity_days": "1-2", "diet": "fair", "sleep_hours": "5-6", "stress": "moderate", "tobacco": "former", "alcohol": "2-4_month"}',
   '{"allergies": "none_known", "medications": []}',
   '{"chief_complaint": null}',
   '{"stress": "moderate", "sleep": "poor"}',
   'da7a0001-0000-0000-0000-000000000001',
   '2026-09-18 09:03:00'),

  ('bbbb0002-0000-0000-0000-000000000002',
   '55555555-5555-5555-5555-555555555555',
   70, 165, 68, 'A+', 'white', 25.0,
   '{"conditions": [], "notes": null}',
   '{"activity_days": "3-4", "diet": "good", "sleep_hours": "7-8", "stress": "low", "tobacco": "never", "alcohol": "monthly_or_less"}',
   '{"allergies": "penicillin", "medications": [{"name": "Amlodipine", "dose": "5mg", "freq": "once daily", "reason": "blood pressure"}]}',
   '{"chief_complaint": null}',
   '{}',
   NULL,
   '2026-09-18 09:08:00');

-- ---------------------------------------------------------------------
-- 5. POLICIES (context, not the product). EXISTING users.
--    u4 deliberately holds TWO overlapping health policies -> redundant alert
-- ---------------------------------------------------------------------
INSERT INTO policies (id, user_id, policy_type, status, coverage_summary, includes_services, renewal_date) VALUES
  -- u2 (senior existing): one active health policy, renewal imminent
  ('cccc0001-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
   'health', 'active', 'Comprehensive health cover incl. annual health assessment.',
   '["health_assessment","digital_gp"]', '2026-10-05'),

  -- u3: active health policy
  ('cccc0002-0000-0000-0000-000000000002', '33333333-3333-3333-3333-333333333333',
   'health', 'active', 'Core health cover with digital GP.',
   '["digital_gp"]', '2027-01-15'),

  -- u4: TWO overlapping health policies (redundant) + a dental policy
  ('cccc0003-0000-0000-0000-000000000003', '44444444-4444-4444-4444-444444444444',
   'health', 'active', 'Comprehensive health cover A.',
   '["health_assessment","digital_gp"]', '2026-12-01'),
  ('cccc0004-0000-0000-0000-000000000004', '44444444-4444-4444-4444-444444444444',
   'health', 'active', 'Comprehensive health cover B (overlaps A).',
   '["health_assessment","digital_gp"]', '2027-03-01'),
  ('cccc0005-0000-0000-0000-000000000005', '44444444-4444-4444-4444-444444444444',
   'dental', 'active', 'Routine dental cover.',
   '[]', '2027-02-10');

-- ---------------------------------------------------------------------
-- 6. CLAIMS
-- ---------------------------------------------------------------------
INSERT INTO claims (id, user_id, policy_id, claim_type, filed_at, status) VALUES
  ('dddd0001-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
   'cccc0001-0000-0000-0000-000000000001', 'physiotherapy', '2026-05-12 11:00:00', 'settled'),
  ('dddd0002-0000-0000-0000-000000000002', '44444444-4444-4444-4444-444444444444',
   'cccc0003-0000-0000-0000-000000000003', 'consultation', '2026-07-02 09:30:00', 'settled'),
  ('dddd0003-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333',
   'cccc0002-0000-0000-0000-000000000002', 'digital_gp', '2026-08-20 16:20:00', 'settled');

-- ---------------------------------------------------------------------
-- 7. HEALTH_EVENTS (feeds "health status" OPs + gap detection)
--    u1: NO assessment on file -> "no assessment" gap
--    u2: last assessment 2025-03-10 (~18 months ago) -> overdue gap
--    u3: seeded lifestyle/wellbeing risk flags (existing user, no survey)
--    u4/u5: recent assessments (no assessment gap)
-- ---------------------------------------------------------------------
INSERT INTO health_events (id, user_id, event_type, event_date, result_summary, risk_flags, source, notes) VALUES
  ('eeee0002-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222',
   'assessment', '2025-03-10', 'General health within normal range; BP slightly elevated.',
   '{"bp": "borderline"}', 'seeded', 'Last full assessment.'),

  ('eeee0003-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333',
   'consultation', '2026-08-20', 'Reported fatigue, low activity and work stress.',
   '{"activity": "sedentary", "stress": "high", "sleep": "poor"}', 'seeded', 'Digital GP note.'),

  ('eeee0004-0000-0000-0000-000000000004', '44444444-4444-4444-4444-444444444444',
   'assessment', '2026-06-15', 'Assessment normal.', '{}', 'seeded', 'Recent assessment.'),

  ('eeee0005-0000-0000-0000-000000000005', '55555555-5555-5555-5555-555555555555',
   'screening', '2026-01-20', 'Routine BP check, on medication, controlled.',
   '{"bp": "controlled"}', 'seeded', 'Self-reported at signup.');
  -- NB: u1 intentionally has NO health_events -> triggers "no assessment on file".

-- ---------------------------------------------------------------------
-- 8. CLINICAL_SIGNALS (MedGemma stage-1 output; NEVER shown to user directly)
--    passed_guardrail = true means the deterministic guardrail approved it.
-- ---------------------------------------------------------------------
INSERT INTO clinical_signals (id, user_id, report_id, signal_type, value, confidence, passed_guardrail, extracted_at) VALUES
  -- u1 (hero): no assessment + family history
  ('ffff0001-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
   'da7a0001-0000-0000-0000-000000000001', 'assessment_overdue',
   '{"last_assessment_date": null, "months_since": null}', 0.98, true, '2026-09-18 09:03:10'),
  ('ffff0002-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111',
   'da7a0001-0000-0000-0000-000000000001', 'family_history_flag',
   '{"condition": "type2_diabetes", "relative": "father"}', 0.95, true, '2026-09-18 09:03:11'),

  -- u2: overdue assessment (18 months)
  ('ffff0003-0000-0000-0000-000000000003', '22222222-2222-2222-2222-222222222222',
   NULL, 'assessment_overdue',
   '{"last_assessment_date": "2025-03-10", "months_since": 18}', 0.97, true, '2026-09-18 06:00:00'),

  -- u3: lifestyle risk + wellbeing flag
  ('ffff0004-0000-0000-0000-000000000004', '33333333-3333-3333-3333-333333333333',
   NULL, 'lifestyle_risk',
   '{"flags": ["sedentary"]}', 0.90, true, '2026-09-18 06:00:00'),
  ('ffff0005-0000-0000-0000-000000000005', '33333333-3333-3333-3333-333333333333',
   NULL, 'wellbeing_flag',
   '{"flags": ["high_stress","poor_sleep"]}', 0.88, true, '2026-09-18 06:00:00');

-- ---------------------------------------------------------------------
-- 9. RECOMMENDATIONS (guardrail-approved, transparent — spec §5.2)
--    Every row carries service + reason + trigger_data + next_step.
-- ---------------------------------------------------------------------
INSERT INTO recommendations (id, user_id, signal_id, service, reason, trigger_data, next_step, status, created_at) VALUES
  -- u1 hero: two recommendations
  ('99990001-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
   'ffff0001-0000-0000-0000-000000000001', 'Health Assessment',
   'Recommended because there is no health assessment on file and you reported relevant risk factors.',
   '{"last_assessment_date": null, "risk_factors": ["family_history_diabetes"]}',
   'Explore assessment availability', 'shown', '2026-09-18 09:03:20'),
  ('99990002-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111',
   'ffff0002-0000-0000-0000-000000000002', 'Genomic Health',
   'Recommended because a first-degree family history of type 2 diabetes may warrant discussing genomic screening with a clinician.',
   '{"family_history": "type2_diabetes", "relative": "father"}',
   'Learn about Genomic Health', 'shown', '2026-09-18 09:03:21'),

  -- u2 overdue
  ('99990003-0000-0000-0000-000000000003', '22222222-2222-2222-2222-222222222222',
   'ffff0003-0000-0000-0000-000000000003', 'Health Assessment',
   'Recommended because your last assessment was about 18 months ago.',
   '{"last_assessment_date": "2025-03-10", "months_since": 18}',
   'Book your next health assessment', 'shown', '2026-09-18 06:00:10'),

  -- u3 lifestyle + mental health
  ('99990004-0000-0000-0000-000000000004', '33333333-3333-3333-3333-333333333333',
   'ffff0004-0000-0000-0000-000000000004', 'Personalised Health Programme',
   'Recommended because your reported activity level suggests a preventive fitness programme may help.',
   '{"lifestyle_flags": ["sedentary"]}',
   'Explore the Personalised Health Programme', 'shown', '2026-09-18 06:00:11'),
  ('99990005-0000-0000-0000-000000000005', '33333333-3333-3333-3333-333333333333',
   'ffff0005-0000-0000-0000-000000000005', 'Early Mental Health Support',
   'A few of your answers suggest early mental-health support could be worth exploring.',
   '{"wellbeing_flags": ["high_stress","poor_sleep"]}',
   'See mental-health support options', 'shown', '2026-09-18 06:00:12'),

  -- u4 non-recommended / duplicate policy (recommender rule, no clinical signal)
  ('99990006-0000-0000-0000-000000000006', '44444444-4444-4444-4444-444444444444',
   NULL, 'Policy review (non-recommended)',
   'You hold two overlapping comprehensive health policies with duplicate benefits; consolidating may avoid paying twice.',
   '{"overlapping_policies": ["cccc0003","cccc0004"], "duplicate_services": ["health_assessment","digital_gp"]}',
   'Review overlapping cover', 'shown', '2026-09-18 06:00:13');

-- ---------------------------------------------------------------------
-- 10. NOTIFICATIONS (Trigger/Action output, polled by Chat UI)
-- ---------------------------------------------------------------------
INSERT INTO notifications (id, user_id, type, service_family, message, triggered_at, read) VALUES
  ('88880001-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
   'checkup_reminder', 'health_assessment',
   'Based on your report, a health assessment could be a good next step.', '2026-09-18 09:03:30', false),

  ('88880002-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222',
   'assessment_due', 'health_assessment',
   'Your last health assessment was 18 months ago — you may be due for another.', '2026-09-18 06:00:20', false),
  ('88880003-0000-0000-0000-000000000003', '22222222-2222-2222-2222-222222222222',
   'renewal_alarm', NULL,
   'Your health policy renews on 5 Oct 2026.', '2026-09-18 06:00:21', false),

  ('88880004-0000-0000-0000-000000000004', '33333333-3333-3333-3333-333333333333',
   'mh_checkin', 'mental_health',
   'A quick wellbeing check-in might be worthwhile — support is available whenever you need it.', '2026-09-18 06:00:22', false),

  ('88880005-0000-0000-0000-000000000005', '44444444-4444-4444-4444-444444444444',
   'non_recommended_alert', NULL,
   'Two of your health policies appear to overlap — it may be worth reviewing them.', '2026-09-18 06:00:23', false);

-- ---------------------------------------------------------------------
-- 11. INTERACTION_LOG (BigQuery export / analytics + impact counters §16)
-- ---------------------------------------------------------------------
INSERT INTO interaction_log (id, user_id, ip_code, op_code, mechanism, service_recommended, logged_at) VALUES
  ('77770001-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'IP1', 'OP1', 'genai',       'Health Assessment', '2026-09-18 09:03:25'),
  ('77770002-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 'IP2', 'OP2', 'recommender', 'Genomic Health',    '2026-09-18 09:03:40'),
  ('77770003-0000-0000-0000-000000000003', '22222222-2222-2222-2222-222222222222', 'IP1', 'OP1', 'recommender', 'Health Assessment', '2026-09-18 06:00:30'),
  ('77770004-0000-0000-0000-000000000004', '33333333-3333-3333-3333-333333333333', 'IP1', 'OP2', 'recommender', 'Personalised Health Programme', '2026-09-18 06:00:31'),
  ('77770005-0000-0000-0000-000000000005', '44444444-4444-4444-4444-444444444444', 'IP4', 'OP4', 'recommender', 'Policy review (non-recommended)', '2026-09-18 06:00:32');

COMMIT;

-- =====================================================================
-- Quick sanity checks (optional — run after seeding):
--   SELECT user_type, COUNT(*) FROM users GROUP BY user_type;              -- 2 new, 3 existing
--   SELECT COUNT(*) FROM preventive_services;                              -- 5
--   SELECT COUNT(*) FROM clinical_signals WHERE passed_guardrail;          -- 5  (impact counter)
--   SELECT COUNT(DISTINCT user_id) FROM recommendations;                   -- 4
--   -- Hero user u1 should have NO health_events (drives the "no assessment" gap):
--   SELECT COUNT(*) FROM health_events WHERE user_id = '11111111-1111-1111-1111-111111111111';  -- 0
-- =====================================================================
