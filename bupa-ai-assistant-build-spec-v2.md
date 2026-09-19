# Bupa Preventive Health Assistant — Build Specification (v2)

> **Purpose of this file**: a self-contained brief for building the project end to end. It can be pasted into Antigravity, Claude Code, or any other AI coding assistant to generate the actual codebase. It assumes access to a Google Cloud sandbox project (`@gcplab.me` credentials) with Cloud Run, Cloud SQL/AlloyDB, Cloud Storage, BigQuery, Vertex AI (**Gemini + MedGemma via Model Garden**), Cloud Scheduler, and Pub/Sub already available.
>
> **What changed from v1**: reframed from an insurance-policy chatbot into a **preventive-health-services concierge**, per the Health × AI Hackathon (Adeline Sprint, London, 18 Sept 2026, Google HQ — *Powered by Google MedGemma*) brief. MedGemma is now central, not optional. Bupa's five named preventive service families — health assessments, genomic health, digital consultations, personalised health programmes, and early mental health support — are first-class objects in the data model and flows.

---

## 0. Hackathon brief this build must satisfy

> Healthcare is evolving from treating illness to helping people stay healthy for longer. Bupa already offers a range of preventive healthcare services — health assessments, genomic healthcare programmes, digital consultations, personalised health programmes and early mental health support. The opportunity isn't to create new preventive services, but to help people **discover, understand and engage** with the right services at the right time. Build an AI-powered solution that helps people engage with preventive healthcare through more personalised, timely and relevant experiences, empowering them to take action **before they become unwell**. *(Powered by Google MedGemma.)*

**Direct mapping — how this build answers the brief:**

| Brief keyword | Product pillar | Mechanism that delivers it |
|---|---|---|
| **Discover** the right service | **Teach** | Recommendation Engine matches user → preventive service |
| **Understand** it | **Explain** | GenAI (Gemini) plain-language summaries; MedGemma for clinical inputs |
| **Engage at the right time** | **Aware** | Trigger/Action nudges (Cloud Scheduler + Pub/Sub) |
| Personalised / timely / relevant | all three | Survey + health history + risk rules drive every output |
| Act **before becoming unwell** | Preventive-gap detection | Rule engine + MedGemma flag gaps and recommend action |
| **Powered by MedGemma** | Clinical interpretation | MedGemma reads assessment results / screeners / documents |

---

## 1. Problem statement

Bupa already offers excellent preventive services, but people don't **discover, understand, or engage** with them at the right moment. Engagement is reactive — users interact with their insurer only when something has already gone wrong (a claim). The gap isn't the services; it's the **matching, timing, and comprehension** layer that connects a person to the right preventive service *before* they become unwell.

## 2. Mission

Three words define the product: **Teach | Explain | Aware** — which map directly onto the brief's **discover | understand | engage**.

- **Teach (Discover)** — surface the preventive services a user is eligible for or would benefit from but doesn't know they have access to.
- **Explain (Understand)** — turn dense health data, assessment results, and service descriptions into plain-language, personalized summaries.
- **Aware (Engage)** — proactively nudge users toward timely preventive action (screenings, checkups, mental-health check-ins, renewals) instead of waiting for them to log in.

## 3. Bupa preventive service families (the catalog we help people discover)

These are the real, publicly described Bupa preventive offerings the assistant recommends. Seeded as a catalog (see §8); **no real member data is used** — only the public service descriptions plus mock user records.

| Service family | What it is | Typical trigger to recommend it |
|---|---|---|
| **Health Assessment** | Structured health MOT (bloods, biometrics, lifestyle review) | Age ≥ 40, no assessment in 12–24 mo, risk flags |
| **Genomic Health** | Genomic/DNA-based risk screening & personalised prevention | Family history flag, proactive-health interest |
| **Digital GP / Consultations** | On-demand video/phone GP appointments | Symptom query, convenience need, follow-up |
| **Personalised Health Programme** | Ongoing coaching for weight, fitness, nutrition, chronic-risk | Lifestyle flags (BMI, smoking, low activity) |
| **Early Mental Health Support** | Direct-access mental health assessment & talking therapies | Stress/mood/sleep flags, screener score |

## 4. User segments

| Segment | Defining trait | Primary need |
|---|---|---|
| **New user** | No account history | Discovery — "which preventive services fit someone like me" |
| **Existing user** | Has policies/claims/health events on file | Personalization — "what preventive action should *I* take next" |

---

## 5. Input → Output logic (source of truth for behavior)

### A. New user flow (entry point: pre-survey)

```
Pre-survey entry — TWO ways to start:

  (a) UPLOAD MEDICAL RECORDS (optional shortcut)
      User uploads medical report(s) / discharge summary / assessment PDF/image
        ↓
      MedGemma extracts structured fields → PRE-FILLS the survey
        ↓
      User reviews, cross-checks, and EDITS any pre-filled answer before submitting
        (nothing is trusted blindly — human-in-the-loop confirmation)

  (b) FILL MANUALLY
      User answers the survey directly.

Survey scope (full checklist in Appendix A):
  - MANDATORY: Section 1 core — Age, Height, Weight, Blood Type
  - OPTIONAL:  ethnicity; family history; lifestyle & habits; medications &
              allergies; current symptoms / chief complaint
  ↓
IP1 → Explore preventive services (Start / Intro)
  OP1 → Personalised health overview + top recommended preventive services
        (shaped by survey answers; MedGemma interprets any clinical/screener input)

IP2 → "What should I do first?"
  OP2 → Ranked preventive-service recommendations with plain-language reasons
```

> **Upload → pre-fill → confirm** is a headline MedGemma moment: the model reads a real-looking medical document and turns it into a structured, editable survey. Always surface pre-filled values as *suggestions the user confirms or edits* — never auto-submit MedGemma output.

### B. Existing user flow (entry point: account history, no survey needed)

```
IP1 → My health status
  OP1 → Personalised health overview (from health events / assessment history)

IP2 → My preventive services & coverage
  OP2 → Gaps + reminders (e.g. "assessment overdue", "mental-health check-in")

IP3 → Understand a result / document
  OP3 → MedGemma-interpreted plain-language explanation + recommended next service

IP4 → My claims / history
  OP4 → Preventive-service recommendation or non-recommended/duplicate alert
```

**Rule of thumb**: for a New User the pre-survey plays the role that health/claims history plays for an Existing User — it is the seed data everything downstream personalizes against. If the survey is skipped or thin, OP1 degrades to generic content.

---

## 6. The four AI mechanisms

| # | Mechanism | Role | Primary service |
|---|---|---|---|
| 1 | **Prompt** | Captures and parses raw user intent/query | App logic on Cloud Run (no model call) |
| 2 | **GenAI** | Generates personalized health summaries, service explanations, recommendation reasoning | **Gemini** (Vertex AI) |
| 3 | **Clinical Interpretation & Extraction** | (a) Extracts structured fields from uploaded medical records to **pre-fill the survey** (user-editable); (b) reads assessment results, screener answers, or documents/images and turns them into plain-language risk signals | **MedGemma** (Vertex AI Model Garden) — **central, not optional** |
| 4 | **Trigger/Action** | Sends timely nudges — assessment-due alerts, checkup reminders, mental-health check-ins, renewals | Cloud Scheduler (timed checks) + Pub/Sub (event fan-out) |
| 5 | **Recommendation Engine** | Matches user → preventive services; flags gaps, duplicates, non-recommended plans | Rule logic on Cloud Run reading Cloud SQL/AlloyDB; reasoning upgradeable with Gemini |

> MedGemma is now its own mechanism (Clinical Interpretation) so the "Powered by MedGemma" requirement is demonstrably central. Every flow that touches a clinical result, symptom description, or wellbeing screener routes through MedGemma before Gemini phrases the final answer.

---

## 7. Architecture

```
[Pre-survey]  [Account history]  [Uploaded result / screener]
      \             |                   /
       \            |                  /
        v           v                 v
                [ Chat UI ]
          Cloud Run + Firebase Hosting
                    |
                    v
            [ Intent & user router ]
      Gemini — classifies new/existing + IP
                    |
   -----------+-----------+-------------+-------------+
   |          |           |             |             |
[Prompt]  [GenAI]   [MedGemma]   [Recommender] [Trigger/Action]
          Gemini    clinical      preventive     Scheduler+PubSub
                    interpret     matching
             |          |             |             |
             +------ reads/writes data layer -------+
                          |
        -----------------+------------------
        |                |                 |
[Cloud SQL/AlloyDB] [Cloud Storage]  [BigQuery + Looker]
  users, policies      assessment      analytics
  claims, health       docs/images,
  events, services     screener PDFs

Response flows back up through the router to the Chat UI.
```

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

-- pre_survey_responses (New User path only). Full question set in Appendix A.
-- Section 1 core fields are MANDATORY; everything else is optional / nullable.
CREATE TABLE pre_survey_responses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  -- Section 1: Basic Information (MANDATORY core)
  age INT NOT NULL,
  height_cm NUMERIC NOT NULL,
  weight_kg NUMERIC NOT NULL,
  blood_type TEXT NOT NULL,
  ethnicity TEXT,                       -- optional
  bmi NUMERIC,                          -- derived from height/weight
  -- Section 2-5: optional, stored as structured JSONB blocks
  family_history JSONB,                 -- {"conditions":["heart_disease","type2_diabetes"], "notes":"..."}
  lifestyle JSONB,                      -- activity, nutrition, hydration, sleep, stress, tobacco, alcohol
  medications_allergies JSONB,          -- allergies + medication list
  symptoms JSONB,                       -- chief complaint, onset, timing, severity, better/worse
  wellbeing_flags JSONB,                -- {"stress":"high","sleep":"poor"} derived shortcut for mental-health path
  -- Provenance: was any of this pre-filled from an uploaded record?
  prefilled_from_upload BOOLEAN DEFAULT false,
  source_document_id UUID,              -- REFERENCES uploaded_documents(id) if pre-filled
  submitted_at TIMESTAMP DEFAULT now()
);

-- uploaded_documents (medical records the user uploads; feeds MedGemma extraction)
CREATE TABLE uploaded_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  storage_uri TEXT,                     -- Cloud Storage path to the PDF/image
  doc_type TEXT,                        -- medical_report | discharge_summary | assessment_result | other
  extracted_fields JSONB,               -- MedGemma structured output used to pre-fill the survey
  uploaded_at TIMESTAMP DEFAULT now()
);

-- preventive_services (PUBLIC catalog — the services we help people discover)
CREATE TABLE preventive_services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_family TEXT,                  -- health_assessment | genomic_health | digital_gp | health_programme | mental_health
  name TEXT,
  description TEXT,                      -- plain-language, from Bupa public pages
  eligibility_rule JSONB,               -- machine-readable rule the recommender evaluates
  typical_cadence_months INT            -- e.g. health assessment ~ every 12-24 months
);

-- policies (context, not the product)
CREATE TABLE policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  policy_type TEXT,                     -- health, dental, life, etc.
  status TEXT,                          -- active, lapsed, pending
  coverage_summary TEXT,
  includes_services JSONB,              -- which preventive_services this policy already unlocks
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

-- health_events (self-reported, seeded, or MedGemma-derived; feeds "health status" OPs)
CREATE TABLE health_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  event_type TEXT,                     -- assessment, screening, vaccination, consultation, mh_checkin
  event_date DATE,
  result_summary TEXT,                 -- plain-language result (may be MedGemma output)
  risk_flags JSONB,                    -- {"bp": "elevated", "cholesterol": "borderline"}
  source TEXT,                         -- seeded | user_upload | medgemma
  notes TEXT
);

-- notifications (Trigger/Action output, polled by Chat UI)
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  type TEXT,                           -- assessment_due, checkup_reminder, mh_checkin, renewal_alarm, non_recommended_alert
  service_family TEXT,                 -- which preventive service the nudge points to
  message TEXT,
  triggered_at TIMESTAMP DEFAULT now(),
  read BOOLEAN DEFAULT false
);

-- interaction_log (for BigQuery export / analytics)
CREATE TABLE interaction_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  ip_code TEXT,                        -- IP1, IP2...
  op_code TEXT,                        -- OP1, OP2...
  mechanism TEXT,                      -- prompt | genai | medgemma | recommender | trigger_action
  service_recommended TEXT,            -- service_family recommended, if any
  logged_at TIMESTAMP DEFAULT now()
);
```

**Seed data**: 3–5 fake users (mix of New and Existing) with varied policies/claims/health events, **plus the full `preventive_services` catalog** (the five Bupa families, populated from public descriptions). Do this before building anything else — it unblocks every downstream feature without real integrations.

> **Sourcing note (see also the reply in chat)**: the `preventive_services` catalog is built from Bupa's **public** website descriptions — this is legitimate and is exactly the "help people discover existing services" the brief asks for. All member-side data (users, policies, claims, health events) is **mock/seeded**. No real Bupa member data is used.

---

## 9. API surface (Cloud Run service)

| Endpoint | Method | Purpose |
|---|---|---|
| `POST /survey/upload` | POST | Upload a medical record → **MedGemma extracts fields** → returns a pre-filled (editable) survey draft; stores the doc in Cloud Storage + `uploaded_documents` |
| `POST /survey` | POST | Submit pre-survey answers (whether typed manually or user-confirmed after pre-fill). Validates Section 1 mandatory fields |
| `POST /chat` | POST | Main entry — body `{user_id, message}`; router classifies user_type + IP, dispatches to a mechanism, returns OP |
| `POST /interpret` | POST | Upload a health-assessment result / screener / document → **MedGemma** returns plain-language interpretation + risk flags |
| `GET /user/{id}/status` | GET | Health status overview (OP1 both flows) |
| `GET /services` | GET | The preventive-services catalog (discovery) |
| `GET /user/{id}/recommendations` | GET | Ranked preventive-service recommendations for this user |
| `GET /user/{id}/policies` | GET | List policies (context) |
| `GET /user/{id}/claims` | GET | Claims history |
| `GET /user/{id}/notifications` | GET | Poll for nudges written by Trigger/Action |
| `POST /internal/trigger-check` | POST | Called by Cloud Scheduler daily — checks assessment cadence, checkup gaps, mental-health check-ins, renewals; writes to `notifications`, publishes to Pub/Sub |

### `/chat` request/response contract

```json
// Request
{ "user_id": "uuid", "message": "I've been feeling stressed and not sleeping" }

// Response
{
  "ip_matched": "IP1",
  "user_type": "existing",
  "op_code": "OP1",
  "response_text": "Thanks for sharing that. Based on what you've described...",
  "recommendations": [
    { "service_family": "mental_health", "reason": "reported high stress and poor sleep" }
  ],
  "mechanism_used": "recommender",
  "clinical_interpretation_used": true
}
```

### `/interpret` request/response contract (MedGemma)

```json
// Request  (result text, screener answers, or a Cloud Storage doc/image ref)
{ "user_id": "uuid", "input_type": "assessment_result", "content": "BP 148/92, LDL 4.1..." }

// Response
{
  "plain_language": "Your blood pressure and cholesterol are a little above the healthy range...",
  "risk_flags": { "bp": "elevated", "cholesterol": "borderline" },
  "recommended_service": "health_programme",
  "model": "medgemma"
}
```

### `/survey/upload` request/response contract (MedGemma pre-fill)

```json
// Request  (multipart: medical record file + user_id)
// -> stored in Cloud Storage, row written to uploaded_documents

// Response — a survey DRAFT the user reviews and edits before POST /survey
{
  "document_id": "uuid",
  "prefilled": true,
  "confidence_note": "Extracted from your uploaded report — please review and correct anything wrong.",
  "survey_draft": {
    "age": 52, "height_cm": 178, "weight_kg": 91, "blood_type": "O+",
    "family_history": { "conditions": ["type2_diabetes"] },
    "lifestyle": { "tobacco": "former", "alcohol": "2-4_month" },
    "medications_allergies": { "medications": [ { "name": "Metformin", "dose": "500mg", "freq": "once daily" } ] }
  },
  "fields_not_found": ["stress_level", "physical_activity_days"],
  "model": "medgemma"
}
```

> Every field in `survey_draft` is a **suggestion**. The UI must render it as editable and require the user to confirm before `POST /survey`. Fields MedGemma couldn't find come back in `fields_not_found` for the user to fill in.

---

## 10. GenAI + MedGemma prompt design (prototype in AI Studio first)

**Intent classifier prompt** (feeds the router) — returns structured JSON:
```
System: You are an intent classifier for a preventive-health assistant.
Classify the user's message into one of: IP1_explore_services, IP1_health_status,
IP2_recommendations, IP2_my_services, IP3_interpret_result, IP4_my_claims.
Also state whether this fits a "new" or "existing" user flow, and whether the
message contains a clinical result/symptom/screener that needs MedGemma.
Respond ONLY with JSON: {"ip":"...","flow":"new|existing","needs_clinical":true|false}
```

**Health status summary prompt** (GenAI / Gemini):
```
System: You are a friendly preventive-health assistant for Bupa. Given the
user's survey answers or health history below, write a 3-4 sentence plain-language
overview. Avoid medical jargon. If data suggests a preventive-service gap, name
the specific Bupa service (health assessment, genomic health, digital GP,
personalised health programme, or mental health support) and why it fits.
Data: {user_context_json}
```

**Record-extraction / survey pre-fill prompt** (MedGemma — powers `/survey/upload`):
```
System: You extract structured health data from an uploaded medical record to
pre-fill a health survey. Read the document below and return ONLY JSON matching
the survey schema: age, height_cm, weight_kg, blood_type, ethnicity,
family_history{conditions[],notes}, lifestyle{...}, medications_allergies{...},
symptoms{...}. For any field not present in the document, OMIT it (do not guess).
Also return "fields_not_found": [ ... ] listing schema fields you could not fill.
These values are suggestions the user will review and correct — do not diagnose.
Document: {document_text_or_image}
```

**Clinical interpretation prompt** (MedGemma — Clinical Interpretation mechanism):
```
System: You are a clinical interpretation assistant. Given the health-assessment
result, screener answers, or document text below, extract: (1) a plain-language
explanation a non-clinician can understand, (2) structured risk_flags, (3) the
single most relevant preventive service to recommend next. Do NOT diagnose or
give treatment advice — frame everything as "consider discussing / booking".
Input: {clinical_input}
```

**Recommendation reasoning prompt** (Recommendation Engine — Gemini upgrade):
```
System: Given this user's profile, health events, current policies, and the
preventive-services catalog, identify: (1) preventive-service gaps, (2) the top
2-3 services to recommend with a one-line reason each, (3) any existing plan that
looks redundant or non-recommended. Return concise bullet points.
Data: {user_json}, {health_events_json}, {services_catalog_json}
```

Keep all prompts under version control as separate files (`/prompts/*.md`) so they iterate independently of app code.

---

## 11. Build order (recommended sequence)

1. **Schema + seed data** — stand up Cloud SQL/AlloyDB, run the schema, insert 3–5 fake users **and the preventive-services catalog**.
2. **Cloud Run API shell** — deploy a bare service with all endpoints stubbed (mock JSON). Deploy early so something is always live to demo.
3. **Prompt prototyping in AI Studio** — nail all four prompts (incl. MedGemma clinical interpretation) before wiring in.
4. **Intent router** — wire the classifier into `/chat`, returning `{ip, flow, needs_clinical}` for test messages.
5. **Wire the five mechanisms** — Prompt (pass-through), GenAI (Gemini), **MedGemma (`/interpret`)**, Recommender (rules + optional Gemini), Trigger/Action (Scheduler → `/internal/trigger-check`).
6. **Pre-survey flow** — build `/survey` (validate mandatory Section 1) + `/survey/upload` (MedGemma extracts fields → editable pre-filled draft). Confirm output changes with survey data present vs absent, and that pre-filled values are user-editable before submit.
7. **MedGemma flow** — build `/interpret`; demo one journey where a seeded assessment result is interpreted into plain language + a service recommendation.
8. **Chat UI** — simple web front end (Firebase Hosting): message pane, quick-reply buttons for the IPs, a **"see my recommended services"** panel, a notifications badge, and a file-upload for the MedGemma demo.
9. **End-to-end test both flows** — New: survey → overview → ranked service recommendations. Existing: status → services/gaps → interpret a result → reminder fires.
10. **Analytics (stretch)** — log every `/chat` to `interaction_log`, export to BigQuery, one Looker chart (e.g. "% of sessions where a preventive service was recommended").
11. **Demo polish** — script two short journeys (one per segment) mapping back to Teach/Explain/Aware (= discover/understand/engage), with MedGemma visibly in the loop.

---

## 12. Services used — full list

| Layer | Service | Used for |
|---|---|---|
| Frontend | **Firebase Hosting** | Serving the chat web app |
| Backend/API | **Cloud Run** | Stateless API (endpoints in §9) |
| Dev environment | **Cloud Shell / Editor** | No local setup; git/python preinstalled |
| Agentic coding | **Antigravity 2.0 / CLI (`agy`)** | Building this codebase |
| Prompt prototyping | **AI Studio** | Fast iteration on prompts |
| LLM — general reasoning | **Gemini** (Vertex AI) | Intent routing, summaries, recommendation reasoning |
| LLM — clinical | **MedGemma** (Vertex AI Model Garden) | **Central** — interpreting results/screeners/documents |
| Structured data | **Cloud SQL** (Postgres) or **AlloyDB** | Users, services, policies, claims, health events, survey |
| Unstructured data | **Cloud Storage** | Assessment PDFs, uploaded results/images for MedGemma |
| Scheduled jobs | **Cloud Scheduler** | Daily checks: assessment cadence, checkup gaps, MH check-ins, renewals |
| Event delivery | **Pub/Sub** | Fan-out from Scheduler to the notification write path |
| Analytics | **BigQuery** | Event log: interactions, recommendations shown, nudges sent |
| Dashboarding | **Looker** | Optional — engagement/impact chart for the demo |

All confirmed available in the provisioned `gcplab.me` sandbox; nothing requires external accounts or billing outside the hackathon environment.

---

## 13. Environment & tooling notes

- Log into `console.cloud.google.com` with `@gcplab.me` credentials; the project is pre-assigned — select it from "Select a project."
- Same credentials work for **AI Studio** and **Antigravity**. For Antigravity, specify the project ID at login to get the Agent Platform (Business) plan — otherwise you'll default to Starter Quota; if you see "Starter Quota," log out and re-enter the project ID.
- Use **Cloud Shell** for all CLI work (git, python, gcloud preinstalled).
- **Do not** commit real API keys — keep secrets in Secret Manager or env vars. Environment is decommissioned after the event; copy anything worth keeping to a persistent place first.
- **Data ethics**: use only Bupa's **public** service descriptions for the catalog and **mock** member data. Do not attempt to access real member/patient records. MedGemma output must be framed as informational ("consider discussing with a clinician"), never as diagnosis.

---

## 14. Suggested repo structure

```
bupa-preventive-assistant/
├── api/                          # Cloud Run service
│   ├── main.py                   # routes in §9
│   ├── router.py                 # intent classification logic
│   ├── mechanisms/
│   │   ├── prompt.py
│   │   ├── genai.py              # Gemini
│   │   ├── medgemma.py           # clinical interpretation
│   │   ├── recommender.py        # preventive-service matching
│   │   └── trigger_action.py
│   ├── db/
│   │   ├── schema.sql            # §8
│   │   └── seed.sql             # fake users + preventive_services catalog
│   └── requirements.txt
├── prompts/
│   ├── intent_classifier.md
│   ├── health_summary.md
│   ├── record_extraction.md      # MedGemma survey pre-fill
│   ├── clinical_interpretation.md
│   └── recommendation.md
├── web/                          # Firebase Hosting front end
│   ├── index.html
│   ├── chat.js
│   ├── survey.html               # full checklist (App. A); Sec 1 mandatory, rest optional
│   └── upload.js                 # medical-record upload → MedGemma pre-fill + result-interpret demo
├── infra/
│   ├── scheduler-job.yaml
│   └── deploy.sh
└── README.md
```

---

## 15. Success criteria for the demo

- [ ] New user can **upload a medical record → MedGemma pre-fills the survey → user edits & confirms**, OR fill the survey manually (only Section 1 is mandatory)
- [ ] New user completes the pre-survey and receives a personalized health overview **plus ranked preventive-service recommendations** (discover)
- [ ] Existing user asks about status/services/claims and gets answers grounded in seeded data (understand)
- [ ] **MedGemma visibly interprets** at least one health-assessment result / screener / document into plain language + a service recommendation (Powered by MedGemma)
- [ ] At least one **preventive** Trigger/Action nudge fires and appears in the UI (assessment-due, checkup, or mental-health check-in)
- [ ] Recommendation Engine matches a user to at least one of the five Bupa service families, or flags a non-recommended/duplicate plan
- [ ] Every output ties back to a named Bupa preventive service (not a generic answer)
- [ ] (Stretch) A BigQuery/Looker chart shows preventive-service engagement across demo users

This file is meant to be handed directly to an AI coding assistant (Antigravity, Claude Code, etc.) with an instruction like: *"Build this project following the spec in bupa-ai-assistant-build-spec-v2.md, starting with section 11's build order."*

---

## Appendix A — Full pre-survey checklist (Adeline Sprint provided)

**Mandatory vs optional**: only **Section 1 core (Age, Height, Weight, Blood Type)** is required. Everything else is optional and may be skipped, filled manually, or pre-filled by MedGemma from an uploaded record (then user-edited). Field types are noted for building the form and the `pre_survey_responses` JSONB blocks.

### Section 1 — Basic Information
- **Age** — numeric — **MANDATORY**
- **Height** — numeric (cm) — **MANDATORY**
- **Weight** — numeric (kg) — **MANDATORY**
- **Blood Type** — choice — **MANDATORY**
- Ethnic group *(optional — helps tailor screenings)*: White · Black/African/Caribbean · Asian · Mixed/Multiple · Other (specify) · Prefer not to say

### Section 2 — Family Medical History *(optional)*
Select all that apply to biological relatives (parents, siblings, children):
- Heart Disease / Heart Attack (esp. before 55) · High Blood Pressure · High Cholesterol · Stroke · Type 2 Diabetes · Type 1 Diabetes · Cancer (specify type + relative) · Kidney Disease · Mental Health Conditions (depression, anxiety, bipolar) · Asthma / COPD · Genetic Disorders (sickle cell, thalassemia, cystic fibrosis) · Dementia / Alzheimer's · None · Unknown/Adopted
- **Notes** — open text: other major family conditions

### Section 3 — Lifestyle & Daily Habits *(optional)*
**Physical activity**
- Days/week of moderate–vigorous activity: 0 · 1–2 · 3–4 · 5+
- Minutes on those days: <15 · 15–30 · 30–60 · >60

**Nutrition & hydration**
- Overall diet: Excellent · Good · Fair · Poor
- Fruit/veg servings per day: 0 · 1–2 · 3–4 · 5+
- Glasses of water/day (≈250 ml): numeric
- Dietary pattern (select all): None · Vegetarian · Vegan · Pescatarian · Halal · Kosher · Low-carb/keto · Intermittent fasting · Medically prescribed · Other

**Sleep & stress**
- Hours of sleep/night: <5 · 5–6 · 7–8 · 9+
- Stress level (past month): Low · Moderate · High · Severe

**Substance use**
- Tobacco/nicotine: Yes daily · Yes occasionally · Former (quit date/length) · Never
- Alcohol: Never · Monthly or less · 2–4×/month · 2–3×/week · 4+×/week

### Section 4 — Current Medications & Allergies *(optional)*
**Allergies** (select all): Medication (specify drug + reaction) · Food (specify + reaction) · Environmental (specify trigger + reaction) · No known allergies · Not sure
**Medications & supplements**: taking any? Yes/No → if yes, list rows of {Medication name, Dosage, Frequency, Reason for taking}

### Section 5 — Current Symptoms & Chief Complaint *(optional)*
- Primary concern / chief complaint — open text
- Onset: <24h · a few days · 1–2 weeks · 1–6 months · >6 months
- Timing: Constant · Intermittent · Progressive
- Severity: slider 0–10 (0 = no pain, 10 = severe)
- What makes it better — open text
- What makes it worse — open text

> These five sections map to the `pre_survey_responses` columns/JSONB in §8: Section 1 → typed columns; Sections 2–5 → `family_history`, `lifestyle`, `medications_allergies`, `symptoms`. `wellbeing_flags` is a derived shortcut (from Section 3 sleep/stress + Section 2 mental-health history) that feeds the mental-health recommendation path.
