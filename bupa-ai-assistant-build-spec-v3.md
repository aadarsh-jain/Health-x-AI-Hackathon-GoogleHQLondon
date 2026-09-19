# Bupa Preventive Health Assistant — Build Specification (v3, definitive)

> **Purpose**: a self-contained brief for building the project end to end. Paste it into Antigravity, Claude Code, or any AI coding assistant to generate the codebase. It assumes a Google Cloud sandbox (`@gcplab.me`) with Cloud Run, Cloud SQL/AlloyDB, Cloud Storage, BigQuery, Vertex AI (**Gemini + MedGemma via Model Garden**), Cloud Scheduler, and Pub/Sub available.
>
> **Lineage**: v3 merges two drafts. From the "preventive-first" draft: the hackathon-brief framing, the five named Bupa preventive service families, and the full survey. From the "gap-detector" draft: the hero feature, the MedGemma→guardrail→Gemini **safety pipeline**, the transparent recommendation object, the 2-minute killer demo, live impact counters, and the path-to-production roadmap. Where they overlapped (report upload / auto-populate), v3 keeps the stronger three-option version.

---

## 0. Hackathon brief this build must satisfy

> Healthcare is evolving from treating illness to helping people stay healthy for longer. Bupa already offers preventive services — health assessments, genomic healthcare programmes, digital consultations, personalised health programmes and early mental health support. The opportunity isn't to create new services, but to help people **discover, understand and engage** with the right services at the right time. Build an AI-powered solution for more personalised, timely and relevant experiences, empowering people to act **before they become unwell**. *(Powered by Google MedGemma.)*

| Brief keyword | Pillar | Delivered by |
|---|---|---|
| **Discover** the right service | **Teach** | Preventive Gap Detector (§3.5) matches user → Bupa service |
| **Understand** it | **Explain** | Gemini plain-language explanation of a transparent recommendation |
| **Engage at the right time** | **Aware** | Trigger/Action nudges (Cloud Scheduler + Pub/Sub) |
| Act **before becoming unwell** | Gap detection | MedGemma signals → guardrail → recommendation |
| **Powered by MedGemma** | Safety pipeline stage 1 | MedGemma extracts clinical signals from reports/survey |

---

## 1. Problem statement

Bupa already offers excellent preventive services, but people don't **discover, understand, or engage** with them at the right moment. Engagement is reactive — users interact with their insurer only once something has gone wrong (a claim). The missing layer is the **matching, timing, and comprehension** that connects a person to the right preventive service *before* they become unwell.

## 2. Mission

**Teach | Explain | Aware** — which map directly onto the brief's **discover | understand | engage**.

- **Teach (Discover)** — surface preventive services the user is eligible for or would benefit from but doesn't know about.
- **Explain (Understand)** — turn dense health data, reports, and service descriptions into plain-language, personalized summaries.
- **Aware (Engage)** — proactively nudge toward timely preventive action instead of waiting for the user to log in.

## 3. User segments

| Segment | Defining trait | Primary need |
|---|---|---|
| **New user** | No account history | Discovery — "which preventive services fit someone like me" |
| **Existing user** | Has policies/claims/health events on file | Personalization — "what preventive action should *I* take next" |

---

## 3.5 Hero feature: Preventive Gap Detection

**This is the one idea the project is remembered for.** Everything else — policies, claims, nudges — supports this single capability:

> "We identify what preventive care you may be missing, explain why, and help you take the next step."

Not a generic healthcare chatbot. A **gap detector with a visible, trustworthy reasoning trail.**

### Concrete gap types (demo at least these 3)

| Gap type | Example trigger | What the user sees |
|---|---|---|
| **Health assessment overdue** | `last_assessment_date` > 12 months, or none on file | "Your last health assessment was 18 months ago." |
| **Personalised programme signal** | Lifestyle flags (sedentary, high stress) match a programme's eligibility rule | "Your reported activity level suggests our preventive fitness programme may help." |
| **Early mental-health signal** | Wellbeing answers cross a configured threshold | "A few of your answers suggest early mental-health support could be worth exploring." |

Every gap is paired with **why it was detected** — the transparency object in §5.2. That reasoning trail is what separates this from a generic chatbot.

## 3.6 Bupa preventive service families (the catalog we help people discover)

The real, publicly described Bupa preventive offerings the assistant recommends. Seeded as a catalog (`preventive_services`, §8) from Bupa's **public** website descriptions — legitimate, and exactly the "help people discover existing services" the brief asks for. All member-side data is **mock/seeded**; no real Bupa member data is used.

| Service family | What it is | Typical trigger to recommend |
|---|---|---|
| **Health Assessment** | Structured health MOT (bloods, biometrics, lifestyle review) | Age ≥ 40, none in 12–24 mo, risk flags |
| **Genomic Health** | Genomic/DNA-based risk screening & personalised prevention | Family-history flag, proactive-health interest |
| **Digital GP / Consultations** | On-demand video/phone GP appointments | Symptom query, convenience need, follow-up |
| **Personalised Health Programme** | Coaching for weight, fitness, nutrition, chronic-risk | Lifestyle flags (BMI, smoking, low activity) |
| **Early Mental Health Support** | Direct-access mental-health assessment & talking therapies | Stress/mood/sleep flags, screener score |

---

## 4. Input → Output logic (source of truth for behavior)

### A. New user flow

```
IP1 → Pro-services (Start/Intro)
  = the pre-survey questionnaire itself, opened with an input-method choice
    (see 4.5): upload a report, pull from records, or fill manually
  User submits answers → written to pre_survey_responses
  OP1 → Health status overview + top recommended preventive services
  = generated by the GenAI pipeline reading the just-submitted answers, same turn

IP2 → Explore Bupa services ("what should I do first?")
  OP2 → Ranked preventive-service recommendations (transparent objects, §5.2)
```

**Important**: there is no separate step before IP1. IP1 *is* the questionnaire — triggering it renders the survey, and the answers become the payload the pipeline reads to produce OP1, in the same request/response cycle.

### 4.5 Report import & auto-populate (like a job portal's "use my resume")

**Problem solved**: a blank form is fine, but if the user already has a health report, screening result, or previous assessment on their device, retyping it is friction — the same friction job portals removed by letting you upload a resume.

**UI** — at the top of IP1 (and for an Existing User starting a new assessment):

```
How would you like to provide your information?
  ○ Upload a report (PDF or image) — we'll fill the form for you
  ○ Select from your Bupa records            [existing users only]
  ○ Fill in manually
```

**Behavior**:
- **Upload a report** → file → Cloud Storage → **MedGemma (multimodal)** extracts structured fields → the survey renders **pre-filled**, every auto-filled field visibly tagged ("from your report") so the user reviews and edits before submitting. **Never auto-submit** without a human check.
- **Select from records** → pulls the most recent `health_events` / `policies` rows and pre-fills the same fields — no upload needed.
- **Fill manually** → the blank form (full checklist in Appendix A). Only **Section 1 (Age, Height, Weight, Blood Type)** is mandatory; everything else optional.

This is the entry point for the killer demo (§15) — the uploaded report is what MedGemma interprets to kick off gap detection.

### B. Existing user flow (entry point: account history, no survey needed)

```
IP1 → Health status info
  OP1 → Health status info (personalized, from claims/policy/health history)

IP2 → My policies & services
  OP2 → Alarm / Reminders (gaps + due preventive actions)

IP3 → Pay / manage Bupa policies
  OP3 → Health status info (updates)

IP4 → My claims
  OP4 → Preventive-service recommendation / non-recommended (duplicate) alert
```

**Rule of thumb**: for a New User, IP1's answers play the role claims/policy history plays for an Existing User — the seed data everything downstream personalizes against. Thin survey → OP1 degrades to generic content.

---

## 5. The four AI mechanisms

| # | Mechanism | Role | Primary service |
|---|---|---|---|
| 1 | **Prompt** | Captures/parses raw user intent | App logic on Cloud Run (no model call) |
| 2 | **GenAI** | A three-stage safety pipeline — see 5.1 | **MedGemma** + guardrail rules + **Gemini** |
| 3 | **Recommendation Engine** ("Preventive Gap Detector") | Turns guardrail-approved signals into a transparent recommendation | Cloud Run rules, reading Cloud SQL/AlloyDB |
| 4 | **Trigger/Action** | Timely nudges — assessment-due, checkup, mental-health check-in, renewal | Cloud Scheduler + Pub/Sub |

### 5.1 GenAI is a pipeline, not a single call — this is the safety architecture

**MedGemma's output must never become the final recommendation directly.** It is a clinical-signal *extractor*, not a decision-maker.

```
MedGemma            →  Clinical signals   →  Safety / guardrail   →  Recommendation    →  Gemini
(extracts from          (structured,           rules                  engine              (writes the
 report/survey)          not prose)             (blocks diagnostic     (decides WHAT        plain-English
                                                  language, reframes    to recommend         explanation the
                                                  as "may warrant       and WHY)              user reads)
                                                  discussing X")
```

1. **MedGemma** reads the uploaded report or survey answers and outputs structured JSON `{signal_type, value, confidence}` — never free-text prose the user could see.
2. **Guardrail rules** (plain deterministic code, not another model call) validate every signal against a clinician-authored allow-list. Output can only ever be framing like *"this may warrant discussing X with a clinician"* — the rules actively block/rewrite anything reading as *"you have X."* This is a hard filter the LLM cannot override.
3. **Recommendation Engine** maps the approved signal to a Bupa service + next step and logs the full trigger chain (§5.2).
4. **Gemini** takes the recommendation object and writes the final plain-English explanation — it never sees raw MedGemma output, only the guardrail-approved recommendation.

The whole point: **no clinical text reaches the user without passing the guardrail layer first**, and that layer is a visible, auditable piece of the architecture — not an assumption in a prompt.

### 5.2 Every recommendation is transparent (not a black box)

Every surfaced recommendation carries all four fields, always shown together:

```json
{
  "service": "Health Assessment",
  "reason": "Recommended because your last assessment was 18 months ago and you reported relevant risk factors.",
  "trigger_data": { "last_assessment_date": "2024-11-02", "risk_factors": ["family_history_diabetes"] },
  "next_step": "Explore assessment availability"
}
```

This is the standard output shape for **every** recommendation, everywhere — not a plain sentence.

---

## 6. Architecture

```
[Upload report]  [Select records]  [Fill manually]   <-- 4.5 input-method choice
        \              |               /
         \             |              /
          v            v             v
              [ Pre-survey / IP1 ]   [Account history]
                    \                     /
                     v                   v
                       [ Chat UI ]
                Cloud Run + Firebase Hosting
                          |
                          v
                [ Intent & user router ]
             Gemini — classifies new/existing + IP
                          |
           -----------+-----------------------+
           |                                  |
       [Prompt]        [GenAI safety pipeline]        [Trigger/Action]
                     MedGemma -> guardrail -> Gemini          |
                              |                               |
                              v                               |
                  [Recommendation Engine]                     |
                  "Preventive Gap Detector"                   |
                     outputs {service, reason,                |
                      trigger_data, next_step}                |
                              |                               |
                  +--- reads/writes data layer ---------------+
                              |
        -----------------------+-----------------------
        |                      |                       |
[Cloud SQL/AlloyDB]     [Cloud Storage]         [BigQuery + Looker]
users, preventive_      policy docs,            analytics + live
services, policies,     uploaded reports        impact counters
claims, clinical_
signals, recommendations

Response (incl. the transparent recommendation object) flows back up to the Chat UI.
```

---

## 7. Services used — full list

| Layer | Service | Used for |
|---|---|---|
| Frontend | **Firebase Hosting** | Serving the chat web app |
| Backend/API | **Cloud Run** | Stateless API (endpoints in §9) |
| Dev environment | **Cloud Shell / Editor** | No local setup; git/python preinstalled |
| Agentic coding | **Antigravity 2.0 / CLI (`agy`)** | Building this codebase |
| Prompt prototyping | **AI Studio** | Fast iteration on prompts |
| LLM — general reasoning | **Gemini** (Vertex AI) | Intent routing; final user-facing explanations |
| LLM — clinical | **MedGemma** (Model Garden) | **Central** — stage 1 of the safety pipeline: extracts structured clinical signals + report fields; never writes user-facing text directly |
| Structured data | **Cloud SQL** (Postgres) / **AlloyDB** | Users, services, policies, claims, health events, survey, clinical signals, recommendations |
| Unstructured data | **Cloud Storage** | Policy PDFs, uploaded health reports (§4.5) |
| Scheduled jobs | **Cloud Scheduler** | Daily checks: assessment cadence, checkup gaps, MH check-ins, renewals |
| Event delivery | **Pub/Sub** | Fan-out from Scheduler to the notification write path |
| Analytics | **BigQuery** | Event log: interactions, recommendations shown, nudges sent |
| Dashboarding | **Looker** | Optional — deeper analytics story |

All confirmed available in the `gcplab.me` sandbox; nothing requires external accounts or billing.

---

## 8. Data model (minimum viable schema)

```sql
-- users
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  user_type TEXT CHECK (user_type IN ('new','existing')) NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);

-- preventive_services (PUBLIC catalog — the services we help people discover)
CREATE TABLE preventive_services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_family TEXT,          -- health_assessment | genomic_health | digital_gp | health_programme | mental_health
  name TEXT,
  description TEXT,             -- plain-language, from Bupa public pages
  eligibility_rule JSONB,      -- machine-readable rule the recommender evaluates
  typical_cadence_months INT
);

-- pre_survey_responses (New User path). Full question set in Appendix A.
-- Section 1 core = MANDATORY; everything else optional / nullable.
CREATE TABLE pre_survey_responses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  age INT NOT NULL,
  height_cm NUMERIC NOT NULL,
  weight_kg NUMERIC NOT NULL,
  blood_type TEXT NOT NULL,
  ethnicity TEXT,
  bmi NUMERIC,                 -- derived
  family_history JSONB,        -- {"conditions":[...], "notes":"..."}
  lifestyle JSONB,             -- activity, nutrition, hydration, sleep, stress, tobacco, alcohol
  medications_allergies JSONB,
  symptoms JSONB,              -- chief complaint, onset, timing, severity, better/worse
  wellbeing_flags JSONB,       -- derived shortcut feeding the mental-health path
  report_id UUID,              -- REFERENCES uploaded_reports(id) if pre-filled
  submitted_at TIMESTAMP DEFAULT now()
);

-- uploaded_reports (section 4.5 — the "resume upload" path)
CREATE TABLE uploaded_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  source TEXT CHECK (source IN ('upload','bupa_records','manual')) NOT NULL,
  file_uri TEXT,               -- Cloud Storage path, null if source != 'upload'
  extraction_status TEXT DEFAULT 'pending', -- pending, parsed, failed
  extracted_json JSONB,        -- MedGemma's structured field extraction (survey pre-fill payload)
  uploaded_at TIMESTAMP DEFAULT now()
);

-- clinical_signals (MedGemma's raw structured output — NEVER shown to the user directly)
CREATE TABLE clinical_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  report_id UUID REFERENCES uploaded_reports(id),
  signal_type TEXT,            -- assessment_overdue, lifestyle_risk, wellbeing_flag, family_history_flag
  value JSONB,
  confidence FLOAT,
  passed_guardrail BOOLEAN DEFAULT false,   -- set by the deterministic guardrail layer
  extracted_at TIMESTAMP DEFAULT now()
);

-- recommendations (guardrail-approved, transparent — see 5.2)
CREATE TABLE recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  signal_id UUID REFERENCES clinical_signals(id),
  service TEXT NOT NULL,       -- maps to a preventive_services.service_family
  reason TEXT NOT NULL,
  trigger_data JSONB NOT NULL,
  next_step TEXT NOT NULL,
  status TEXT DEFAULT 'shown', -- shown, actioned, dismissed
  created_at TIMESTAMP DEFAULT now()
);

-- policies (context, not the product)
CREATE TABLE policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  policy_type TEXT,            -- health, dental, life
  status TEXT,                 -- active, lapsed, pending
  coverage_summary TEXT,
  includes_services JSONB,     -- which preventive_services this policy already unlocks
  renewal_date DATE
);

-- claims
CREATE TABLE claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  policy_id UUID REFERENCES policies(id),
  claim_type TEXT,
  filed_at TIMESTAMP,
  status TEXT
);

-- health_events (seeded/self-reported/MedGemma-derived; feeds "health status" OPs and gap detection)
CREATE TABLE health_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  event_type TEXT,            -- assessment, screening, vaccination, consultation, mh_checkin
  event_date DATE,
  result_summary TEXT,
  risk_flags JSONB,
  source TEXT,                -- seeded | user_upload | medgemma
  notes TEXT
);

-- notifications (Trigger/Action output, polled by Chat UI)
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  type TEXT,                  -- assessment_due, checkup_reminder, mh_checkin, renewal_alarm, non_recommended_alert
  service_family TEXT,
  message TEXT,
  triggered_at TIMESTAMP DEFAULT now(),
  read BOOLEAN DEFAULT false
);

-- interaction_log (for BigQuery export / analytics)
CREATE TABLE interaction_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  ip_code TEXT,
  op_code TEXT,
  mechanism TEXT,             -- prompt | genai | recommender | trigger_action
  service_recommended TEXT,
  logged_at TIMESTAMP DEFAULT now()
);
```

**Seed data**: 3–5 fake users (mix of New and Existing) with varied policies/claims/health events, **plus the full `preventive_services` catalog** (the five families from public descriptions). Do this before building anything else — it unblocks every downstream feature without real integrations.

---

## 9. API surface (Cloud Run service)

| Endpoint | Method | Purpose |
|---|---|---|
| `POST /reports/upload` | POST | Multipart file → Cloud Storage → kicks off MedGemma extraction; returns `report_id` |
| `GET /reports/{id}` | GET | Poll extraction status; once `parsed`, returns `extracted_json` to pre-fill the form |
| `POST /survey` | POST | Submit answers (typed manually or edited from a report's `extracted_json`); validates Section 1 mandatory fields |
| `POST /chat` | POST | Main entry — `{user_id, message}`; router classifies user_type + IP, dispatches, returns OP |
| `GET /services` | GET | Preventive-services catalog (discovery) |
| `GET /user/{id}/status` | GET | Health status overview (OP1 both flows) |
| `GET /user/{id}/policies` | GET | List policies |
| `GET /user/{id}/claims` | GET | Claims history |
| `GET /user/{id}/recommendations` | GET | Transparent recommendation list — each item has `service`, `reason`, `trigger_data`, `next_step` |
| `GET /user/{id}/notifications` | GET | Poll for nudges written by Trigger/Action |
| `GET /impact/summary` | GET | Live counters for the demo (§16) |
| `POST /internal/trigger-check` | POST | Called daily by Cloud Scheduler — checks cadence/gaps/renewals, writes `notifications`, publishes to Pub/Sub |

### `/chat` request/response contract

```json
// Request
{ "user_id": "uuid", "message": "what should I be doing to stay healthy" }

// Response
{
  "ip_matched": "IP2",
  "user_type": "existing",
  "op_code": "OP2",
  "response_text": "Based on your history, one preventive step stands out...",
  "recommendations": [
    { "service": "Health Assessment",
      "reason": "Your last assessment was 18 months ago.",
      "trigger_data": { "last_assessment_date": "2024-11-02" },
      "next_step": "Explore assessment availability" }
  ],
  "mechanism_used": "recommender"
}
```

---

## 10. GenAI prompt design (prototype in AI Studio first)

**Intent classifier** (feeds the router) — returns JSON:
```
System: You are an intent classifier for a preventive-health assistant.
Classify the message into one of: IP1_pro_services, IP1_health_status,
IP2_explore_services, IP2_my_policies, IP3_pay_policies, IP4_my_claims.
State whether this fits a "new" or "existing" user flow, and whether the
message contains a clinical result/symptom needing MedGemma.
Respond ONLY with JSON: {"ip":"...","flow":"new|existing","needs_clinical":true|false}
```

**Report extraction** (MedGemma, multimodal — feeds §4.5 auto-populate):
```
System: Extract structured fields from this uploaded health report or
assessment to pre-fill a survey. Return ONLY JSON matching the survey schema:
age, height_cm, weight_kg, blood_type, ethnicity, family_history{conditions[],notes},
lifestyle{...}, medications_allergies{...}, symptoms{...}. Extraction only — no
interpretation, diagnosis, or commentary. If a field isn't present, OMIT it (do
not guess). Also return "fields_not_found": [ ... ]. These are suggestions the
user will review and correct.
Document: {uploaded_file}
```

**Clinical signal extraction** (MedGemma — stage 1 of the safety pipeline):
```
System: Given this user's survey answers or report data, identify clinical
signals ONLY as structured data — never prose the user reads directly. For each
signal return {signal_type, value, confidence}. Do not phrase anything as a
diagnosis or medical conclusion; that judgment happens downstream, not here.
Data: {user_context_json}
```

**Guardrail rules** (deterministic code, not an LLM prompt — stage 2):
```
For each clinical_signal:
  IF signal_type NOT IN approved_signal_types: DROP (do not pass downstream)
  IF confidence < threshold: DROP or mark low-confidence
  REWRITE framing using only the approved phrase bank, e.g.:
    ALLOWED:  "may warrant discussing {X} with a clinician"
    BLOCKED:  "you have {X}" / "you are at risk of {X}" / any diagnostic verb
  SET passed_guardrail = true; PASS the rewritten signal to the Recommendation Engine
```

**Recommendation reasoning** (Recommendation Engine — stage 3, consumes only approved signals):
```
System: Given this user's guardrail-approved signals, the preventive-services
catalog, current policies, and claims, identify: (1) preventive-service gaps,
(2) a service similar users typically use that this user lacks, (3) any existing
plan that looks redundant. For each, return the transparent object
{service, reason, trigger_data, next_step}. Never restate raw clinical signals
verbatim — reason from them.
Data: {approved_signals_json}, {services_catalog_json}, {policies_json}, {claims_json}
```

**Explanation** (Gemini — stage 4, writes what the user reads):
```
System: Given this recommendation object, write the user-facing explanation in
2-3 plain-language sentences. Use only the "reason" and "next_step" fields — do
not introduce new clinical claims. If it touches a health signal, phrase it as
something that "may warrant discussing with a clinician," never a diagnosis.
Data: {recommendation_json}
```

Keep all under version control as `/prompts/*.md`. The guardrail rules live in `/prompts/guardrail_rules.md` even though they aren't an LLM prompt — the most safety-critical file in the repo, and it deserves the same visibility.

---

## 11. Build order (recommended sequence)

1. **Schema + seed data** — stand up Cloud SQL/AlloyDB, run the schema (incl. `preventive_services`, `uploaded_reports`, `clinical_signals`, `recommendations`), insert 3–5 fake users **and the services catalog**.
2. **Cloud Run API shell** — deploy with all endpoints stubbed (mock JSON). Deploy early so something is always live.
3. **Prompt prototyping in AI Studio** — nail all five prompts + the guardrail rule set. Test guardrails against deliberately "bad" MedGemma outputs to confirm they block diagnostic phrasing.
4. **Report upload path (§4.5)** — `/reports/upload`, Cloud Storage, MedGemma extraction, pre-filled editable form. Build early — it's the entry point for the killer demo.
5. **Intent router** — wire the classifier into `/chat`, returning `{ip, flow, needs_clinical}`.
6. **Safety pipeline + gap detection** — MedGemma → guardrail → Recommendation Engine → Gemini explanation, producing the transparent object end to end. **This is the hero feature — give it the most build time.**
7. **Trigger/Action + remaining mechanisms** — Prompt (pass-through), Cloud Scheduler → `/internal/trigger-check`.
8. **Pre-survey flow** — confirm upload / records / manual all produce the same `pre_survey_responses` shape (Section 1 validated mandatory).
9. **Chat UI** — Firebase Hosting: message pane, quick-reply buttons for the IPs, notifications badge, and recommendation cards showing all four transparency fields. Build against the **accessibility typography system in §18 from the start** (it's far cheaper than retrofitting), with the adult baseline as default and a one-tap Senior Mode toggle; auto-offer Senior Mode when `pre_survey_responses.age >= 65`.
10. **Impact counters (core, not stretch)** — log every `/chat` and recommendation event, expose `/impact/summary`, render at least one live counter (§16).
11. **End-to-end test both flows** — New: upload/select/manual → gap detected → explanation → recommendation → reminder. Existing: status → policies → claims → recommendations → trigger a reminder.
12. **Demo polish** — build the 2-minute killer demo (§15) as the primary walkthrough; the broader tour is secondary.

---

## 12. Environment & tooling notes

- Log into `console.cloud.google.com` with `@gcplab.me`; the project is pre-assigned — select it from "Select a project."
- Same credentials work for **AI Studio** and **Antigravity**. For Antigravity, specify the project ID at login for the Agent Platform (Business) plan — otherwise you default to Starter Quota; if you see "Starter Quota," log out and re-enter the project ID.
- Use **Cloud Shell** for all CLI work (git, python, gcloud preinstalled).
- **Do not** commit real API keys — keep secrets in Secret Manager or env vars. The environment is decommissioned after the event; copy anything worth keeping to a persistent place first.
- **Data ethics**: use only Bupa's **public** service descriptions and **mock** member data. Do not access real member/patient records. MedGemma output is always framed as informational ("consider discussing with a clinician"), never diagnosis.

---

## 13. Suggested repo structure

```
bupa-preventive-assistant/
├── api/                          # Cloud Run service
│   ├── main.py                   # routes in §9
│   ├── router.py                 # intent classification logic
│   ├── mechanisms/
│   │   ├── prompt.py
│   │   ├── genai.py              # MedGemma extract -> guardrail -> Gemini explain
│   │   ├── guardrail.py          # deterministic safety layer (stage 2)
│   │   ├── recommender.py        # Preventive Gap Detector
│   │   └── trigger_action.py
│   ├── db/
│   │   ├── schema.sql            # §8
│   │   └── seed.sql              # fake users + preventive_services catalog
│   └── requirements.txt
├── prompts/
│   ├── intent_classifier.md
│   ├── report_extraction.md
│   ├── clinical_signal.md
│   ├── guardrail_rules.md        # safety-critical (deterministic, not an LLM prompt)
│   ├── recommendation.md
│   └── explanation.md
├── web/                          # Firebase Hosting front end
│   ├── index.html
│   ├── chat.js
│   ├── survey.html               # full checklist (App. A); Sec 1 mandatory
│   ├── upload.js                 # report upload -> pre-fill
│   └── styles/
│       ├── tokens.css            # accessibility design tokens (§18)
│       └── senior-mode.css       # senior-tier overrides (§18)
├── infra/
│   ├── scheduler-job.yaml
│   └── deploy.sh
└── README.md
```

---

## 14. Success criteria for the demo

- [ ] A user can choose upload / select-from-records / manual, and the form auto-populates correctly from an uploaded report (MedGemma pre-fill, user-editable)
- [ ] At least 2 of the 3 gap types (assessment overdue, programme signal, wellbeing signal) fire correctly on seeded data
- [ ] The safety pipeline is visibly distinguishable end to end — a raw MedGemma signal never reaches the UI un-guarded; phrasing is always "may warrant discussing X," never "you have X"
- [ ] Every recommendation shows all four transparency fields: service, reason, trigger data, next step
- [ ] Every output ties back to a named Bupa preventive service (not a generic answer)
- [ ] At least one Trigger/Action nudge fires and appears in the UI
- [ ] The live impact counter (§16) updates in front of the judges during the demo, not just on a slide
- [ ] Existing user can ask about status, policies, and claims and get answers grounded in seeded data
- [ ] UI meets the §18 accessibility bar: body text ≥ 18px, line-height ≥ 1.5, touch targets ≥ 48px, contrast ≥ 7:1, and text stays usable at 200% zoom; Senior Mode toggles cleanly

---

## 15. The 2-minute killer demo (one journey, not a feature tour)

**Don't show everything.** One memorable journey, told once, beats six features shown briefly. Build and rehearse this; the broader walkthrough is secondary.

**Primary journey (New User, ~90s)**:
1. Open IP1 → "Upload a report" → drop in a sample assessment PDF.
2. Form auto-populates from MedGemma's extraction — point out the "from your report" tags, edit one field live to show it's reviewable, not blind auto-submit.
3. Submit → the safety pipeline runs: MedGemma extracts a clinical signal → guardrail rules approve/reframe → Recommendation Engine produces the gap.
4. Screen shows the gap card with all four transparency fields and the guarded phrasing ("may warrant discussing... with a clinician").
5. A proactive reminder appears in the notifications panel — Trigger/Action firing from the same data.

**Secondary journey (Existing User, ~30s)**: ask about claims, show one recommendation with the same transparency schema, show a renewal nudge already in notifications.

This single story hits **discovery** (upload/gap detection), **understanding** (the transparent explanation), and **engagement** (the proactive nudge) in one continuous flow — exactly what judges score for.

---

## 16. Impact metrics — core demo, not a stretch slide

Move at least one into the live demo, not just a dashboard shown afterward:

| Metric | How to compute (even with mock data) |
|---|---|
| Preventive gaps identified | `COUNT(*) FROM clinical_signals WHERE passed_guardrail = true` |
| Users receiving relevant recommendations | `COUNT(DISTINCT user_id) FROM recommendations` |
| Recommendations converted to an action | `COUNT(*) FROM recommendations WHERE status = 'actioned'` |
| Time from signal → recommendation shown | `AVG(recommendations.created_at - clinical_signals.extracted_at)` |

**Simplest implementation**: one `/impact/summary` endpoint running these queries against Cloud SQL directly (no BigQuery export needed for the demo), and a small counter strip in the Chat UI that ticks up as the demo runs — e.g. "3 gaps identified · 2 recommendations shown · 1 actioned." BigQuery + Looker remain the "how would this scale" story if a judge asks.

---

## 17. Path to production

**This spec targets a hackathon/MVP demo — not production.** Not appropriate for real users or real health/claims/payment data until the gaps below close. Phased roadmap:

### Phase 0 — what this spec covers
Working end-to-end demo with seeded fake data, both flows, all four mechanisms wired, one nudge firing, one transparent recommendation surfacing. Good for judges, stakeholder demos, design-partner talks.

### Phase 1 — hardened pilot (real users, non-critical data)
- **Security/compliance**: OAuth2/OIDC auth + sessions (none today); least-privilege IAM per service; secrets in Secret Manager with rotation; audit logging on all reads/writes of `users/policies/claims/health_events/pre_survey_responses`; classify PII/PHI and encrypt those fields at rest; **legal/compliance review** (GDPR / health-data law) before any real data.
- **Reliability**: retries + backoff + circuit breakers around every Vertex AI call; rate-limit `/chat` (abuse + LLM spend); cache expensive GenAI calls; separate staging project/credentials.
- **Data/correctness**: schema migrations (Alembic/Flyway) not static `schema.sql`; input validation on survey + output validation on LLM responses before they reach the user (hallucination is a liability on health content); auditable/explainable recommender reasoning.
- **Product/legal**: visible disclaimer wherever MedGemma-derived content appears (not clinical-grade); explicit consent before collecting survey data or running it through an LLM; WCAG accessibility pass.

### Phase 2 — full production
CI/CD with automated unit/integration/e2e tests; monitoring + alerting + latency SLOs; multi-region/DR + load testing; LLM cost controls (token budgets, per-user caps, spend alerts); formal pen-test + security review; data retention/deletion (right-to-erasure).

### What NOT to skip even for a pilot
The two that can't wait: **authentication** (nothing here should run open) and the **compliance review** (health/insurance data triggers regulatory obligations the moment a real person's data enters the system).

---

## 18. Accessibility & typography — seniors + adults (WCAG-compliant)

This app serves a wide age range including older adults, so legibility and touch accessibility are **functional requirements, not polish**. The system is **two-tier**: an **Adult baseline** that is already accessible, and a **Senior tier** that scales type, spacing, and targets up. Both tiers meet WCAG 2.2; the Senior tier reaches AAA on the metrics that matter most to older eyes (contrast, text size, target size). Ship the baseline as default; auto-offer Senior Mode when `age >= 65` (from the survey) and always expose a manual toggle — never force it, and never assume every older user wants it.

### 18.1 Font family (sans-serif, high legibility)

Older eyes benefit from **open apertures, clear letterform differentiation** (distinguishable `I` / `l` / `1`, `O` / `0`), and generous x-height. Pick a purpose-built accessible sans-serif over a generic geometric one.

| Priority | Typeface | Why |
|---|---|---|
| **1st choice (LOCKED)** | **Atkinson Hyperlegible** | Designed by the Braille Institute specifically for low vision — maximally differentiated letterforms. Free (OFL). **Self-host the font files** (bundle in `web/styles/`), do not load from a CDN at runtime — for privacy, offline reliability, and to avoid a third-party request on a health app. |
| **Alt** | **Lexend** | Engineered to improve reading proficiency; excellent x-height and spacing. Free. |
| **Alt** | **Inter** | Large x-height, tall lowercase, superb screen hinting. Free. |
| Fallback stack | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` | Native rendering if a web font fails to load. |

**Avoid**: condensed faces, decorative/geometric fonts with ambiguous letterforms (e.g. a circular single-story `a`/`g`), and anything where `Il1` collide.

### 18.2 Font weight (rights)

Thin and light weights fail older readers — stroke contrast disappears at low vision.

- **Body**: **Regular 400** (never below 400).
- **Emphasis / labels / buttons**: **Medium 500** or **Semibold 600**.
- **Headings**: **600–700**.
- **Never use** weights **< 400** (no Thin 100 / Light 300) for any text a user must read.
- Do not rely on weight *alone* to convey meaning (WCAG 1.4.1 — use text/icon too).

### 18.3 Minimum pixel sizes

WCAG doesn't hard-mandate a px floor, but evidence-based practice for older adults sets these minimums. "Large text" (for contrast rules) = ≥ 24px regular or ≥ 18.66px bold.

| Element | Adult baseline | **Senior tier** | Floor / rule |
|---|---|---|---|
| Body / chat text | **18px** | **20–22px** | never below 16px, anywhere |
| Secondary / captions | 16px | 18px | 16px hard floor (no 12–14px fine print) |
| Buttons & input labels | 18px | 20px | — |
| Input field text | 18px | 20px | prevents iOS zoom-on-focus at ≥16px |
| H3 | 22px | 26px | — |
| H2 | 26px | 32px | — |
| H1 | 32px | 40px | — |

Use **rem** units on a 16px root so the OS "larger text" setting scales everything. Must satisfy **WCAG 1.4.4 (Resize text)**: fully usable at **200% zoom** with no loss of content or function, and **1.4.10 (Reflow)**: no horizontal scrolling at 320px width — text reflows, never truncates.

### 18.4 Line spacing & text spacing (WCAG 1.4.12)

Older readers lose their place on tight lines; generous leading is one of the highest-impact levers.

- **Line-height (leading)**: **≥ 1.5×** font size for body (Senior tier **1.6–1.75**). Headings may be tighter (1.2–1.3).
- **Paragraph spacing**: **≥ 2×** the font size between paragraphs.
- **Letter-spacing (tracking)**: **≥ 0.12×** font size where adjustable.
- **Word-spacing**: **≥ 0.16×** font size.
- **Line length (measure)**: 45–75 characters; on mobile aim ~35–50. Never full-width edge-to-edge.
- **Alignment**: **left-aligned, ragged right.** Never justify (rivers of whitespace) and never center multi-line body copy.
- **Casing**: sentence case for body; **no ALL-CAPS** for anything longer than a short label (caps destroy word-shape cues).

### 18.5 Colour & contrast (WCAG 1.4.3 / 1.4.11)

- **Text contrast**: Adult baseline **≥ 4.5:1** (AA); **Senior tier ≥ 7:1** (AAA). Large text ≥ 3:1 (AA) / 4.5:1 (AAA).
- **Non-text** (icons, input borders, focus rings, chart strokes): **≥ 3:1** against adjacent colour (1.4.11).
- **Avoid pure `#000` on pure `#fff`** — the halation glare fatigues aging eyes. Use near-black on off-white, e.g. `#1A1A1A` text on `#FAFAFA`. Provide a proper dark theme too (light text on `#121212`, not black).
- **Never encode meaning by colour alone** (1.4.1) — pair a red "overdue" chip with an icon + label. Critical for the gap cards and notification badges.

### 18.6 Touch targets & interaction (WCAG 2.5.8 / 2.5.5)

- **Minimum target**: **44×44px** (WCAG 2.5.5 AAA); **Senior tier 48–56px**. AA (2.5.8) allows 24px — do not settle for that here.
- **Spacing between targets**: ≥ 8px so a shaky tap doesn't hit the wrong control.
- Prefer **large tappable cards/buttons** over small inline links; the quick-reply IP buttons and the survey's multiple-choice options should be full-width tap rows in Senior Mode.
- **Visible focus indicator** (2.4.7) with ≥ 3:1 contrast and ≥ 2px thickness for keyboard/switch users.
- Respect `prefers-reduced-motion` (2.3.3) — no essential info conveyed by animation; keep the impact-counter tick subtle.
- Give inputs real `<label>`s, `inputmode`/`autocomplete` (e.g. numeric keypad for age/height/weight), and clear inline error text (3.3.1) — don't rely on placeholder-only labels.

### 18.7 Implementation — design tokens

Express the two tiers as CSS custom properties so Senior Mode is a single class swap on `<html>` (`web/styles/tokens.css` + `senior-mode.css`):

```css
:root {                     /* Adult baseline */
  --font-sans: "Atkinson Hyperlegible", "Inter", system-ui, sans-serif;
  --fs-body: 1.125rem;      /* 18px */
  --fs-caption: 1rem;       /* 16px */
  --fw-body: 400; --fw-emph: 600;
  --lh-body: 1.5;
  --space-para: 2em;
  --tap-min: 44px;
  --color-text: #1A1A1A; --color-bg: #FAFAFA;   /* ~15:1, off-black on off-white */
  --focus-ring: 2px solid #0B5FFF;
}
html.senior {               /* Senior tier — one class flips everything */
  --fs-body: 1.375rem;      /* 22px */
  --fs-caption: 1.125rem;   /* 18px */
  --lh-body: 1.65;
  --tap-min: 52px;
  /* colours already exceed 7:1; keep or deepen for AAA */
}
body { font-family: var(--font-sans); font-size: var(--fs-body);
       font-weight: var(--fw-body); line-height: var(--lh-body);
       color: var(--color-text); background: var(--color-bg); text-align: left; }
button, .tap { min-height: var(--tap-min); min-width: var(--tap-min); font-size: var(--fs-body); }
:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
p + p { margin-top: var(--space-para); }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
```

> **Demo tie-in**: showing the same recommendation card in Adult vs Senior mode (bigger type, higher contrast, larger tap rows) is a fast, judge-friendly way to prove the "personalised, relevant experiences" claim extends to accessibility — directly on-brief for serving older adults staying healthy for longer.

---

## Appendix A — Full pre-survey checklist (Adeline Sprint provided)

**Mandatory vs optional**: only **Section 1 core (Age, Height, Weight, Blood Type)** is required. Everything else is optional — skippable, fillable manually, or MedGemma-prefilled from an uploaded record (then user-edited). Section 1 → typed columns; Sections 2–5 → `family_history`, `lifestyle`, `medications_allergies`, `symptoms` JSONB blocks.

### Section 1 — Basic Information
- **Age** — numeric — **MANDATORY**
- **Height** — numeric (cm) — **MANDATORY**
- **Weight** — numeric (kg) — **MANDATORY**
- **Blood Type** — choice — **MANDATORY**
- Ethnic group *(optional — helps tailor screenings)*: White · Black/African/Caribbean · Asian · Mixed/Multiple · Other (specify) · Prefer not to say

### Section 2 — Family Medical History *(optional)*
Select all that apply to biological relatives (parents, siblings, children): Heart Disease/Heart Attack (esp. before 55) · High Blood Pressure · High Cholesterol · Stroke · Type 2 Diabetes · Type 1 Diabetes · Cancer (specify type + relative) · Kidney Disease · Mental Health Conditions · Asthma/COPD · Genetic Disorders (sickle cell, thalassemia, cystic fibrosis) · Dementia/Alzheimer's · None · Unknown/Adopted
- **Notes** — open text: other major family conditions

### Section 3 — Lifestyle & Daily Habits *(optional)*
- Days/week moderate–vigorous activity: 0 · 1–2 · 3–4 · 5+
- Minutes on those days: <15 · 15–30 · 30–60 · >60
- Overall diet: Excellent · Good · Fair · Poor
- Fruit/veg servings/day: 0 · 1–2 · 3–4 · 5+
- Glasses of water/day (≈250 ml): numeric
- Dietary pattern (select all): None · Vegetarian · Vegan · Pescatarian · Halal · Kosher · Low-carb/keto · Intermittent fasting · Medically prescribed · Other
- Sleep/night: <5 · 5–6 · 7–8 · 9+ hours
- Stress (past month): Low · Moderate · High · Severe
- Tobacco/nicotine: Yes daily · Yes occasionally · Former (quit date/length) · Never
- Alcohol: Never · Monthly or less · 2–4×/month · 2–3×/week · 4+×/week

### Section 4 — Current Medications & Allergies *(optional)*
- Allergies (select all): Medication (specify + reaction) · Food (specify + reaction) · Environmental (specify + reaction) · No known allergies · Not sure
- Medications & supplements: taking any? Yes/No → if yes, rows of {name, dosage, frequency, reason}

### Section 5 — Current Symptoms & Chief Complaint *(optional)*
- Primary concern / chief complaint — open text
- Onset: <24h · a few days · 1–2 weeks · 1–6 months · >6 months
- Timing: Constant · Intermittent · Progressive
- Severity: slider 0–10
- What makes it better — open text
- What makes it worse — open text

> A symptom entry here should route to **Digital GP consultation**, not a diagnosis — keeping the product on the preventive, before-you're-unwell side of the brief.

---

This file is meant to be handed directly to an AI coding assistant (Antigravity, Claude Code, etc.) with an instruction like: *"Build this project following the spec in bupa-ai-assistant-build-spec-v3.md, starting with section 11's build order."*
