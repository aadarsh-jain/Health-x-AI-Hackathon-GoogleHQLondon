# Bupa AI Assistant — Build Specification

> **Purpose of this file**: this is a self-contained brief for building the project end to end. It can be pasted into Antigravity, Claude Code, or any other AI coding assistant to generate the actual codebase. It assumes access to a Google Cloud sandbox project (`@gcplab.me` credentials) with Cloud Run, Cloud SQL/AlloyDB, Cloud Storage, BigQuery, Vertex AI (Gemini + MedGemma via Model Garden), Cloud Scheduler, and Pub/Sub already available.

---

## 1. Problem statement

Bupa's core problem: users only interact with their insurer reactively — when filing a claim or something has already gone wrong. There is no mechanism that keeps users engaged with their health and coverage *before* they need it.

## 2. Mission

Three words define the product: **Teach | Explain | Aware**

- **Teach** — surface preventive services and coverage the user didn't know they had.
- **Explain** — turn dense policy/claims data into plain-language, personalized summaries.
- **Aware** — proactively nudge users (renewals, checkups, gaps in coverage) instead of waiting for them to log in.

## 3. User segments

| Segment | Defining trait | Primary need |
|---|---|---|
| **New user** | No account history | Discovery — "what can Bupa do for someone like me" |
| **Existing user** | Has policies/claims on file | Personalization — "what's happening with *my* coverage" |

---

## 4. Input → Output logic (source of truth for behavior)

### A. New user flow (entry point: pre-survey)

```
Pre-survey (baseline capture: age bracket, existing conditions y/n,
current insurance y/n, key lifestyle flags — 5 to 8 questions max)
  ↓
IP1 → Pro-services (Start/Intro)
  OP1 → Health status info / overview (generic, shaped by survey answers)

IP2 → All Bupa policies
  OP2 → Suggest Bupa policies
```

### B. Existing user flow (entry point: account history, no survey needed)

```
IP1 → Health status info
  OP1 → Health status info (personalized, from claims/policy history)

IP2 → My policies
  OP2 → Alarm / Reminders

IP3 → Pay all Bupa policies
  OP3 → Health status info (updates)

IP4 → My claims
  OP4 → Another policy application / Non-recommended alert
```

**Rule of thumb**: for a New User, the pre-survey plays the same role that claims/policy history plays for an Existing User — it is the seed data that everything downstream personalizes against. If the survey is skipped or thin, OP1 degrades to generic content.

---

## 5. The four AI mechanisms

| # | Mechanism | Role | Primary service |
|---|---|---|---|
| 1 | **Prompt** | Captures and parses raw user intent/query | App logic on Cloud Run (no model call) |
| 2 | **GenAI** | Generates personalized health summaries, policy explanations, recommendation reasoning | Gemini (Vertex AI); MedGemma via Model Garden for anything touching clinical text/image interpretation |
| 3 | **Trigger/Action** | Sends timely nudges — health alarms, renewal alerts, checkup reminders | Cloud Scheduler (timed checks) + Pub/Sub (event fan-out to notify) |
| 4 | **Recommendation Engine** | Evaluates existing coverage, suggests preventive services, flags non-recommended/duplicate plans | Rule logic on Cloud Run, reading Cloud SQL/AlloyDB; upgradeable with Gemini reasoning |

---

## 6. Architecture

```
[Pre-survey]  [Account history]
      \            /
       \          /
        v        v
         [ Chat UI ]
     Cloud Run + Firebase Hosting
              |
              v
      [ Intent & user router ]
   Gemini — classifies new/existing + IP
              |
   -----------+-----------+-----------+
   |          |           |           |
[Prompt]   [GenAI]  [Recommender] [Trigger/Action]
             |            |            |
             +--- reads/writes data layer ---+
                          |
        -----------------+-----------------
        |                |                |
[Cloud SQL/AlloyDB] [Cloud Storage] [BigQuery + Looker]
  users, policies      policy docs,    analytics
  claims                images

Response flows back up through the router to the Chat UI.
```

---

## 7. Services used — full list

| Layer | Service | Used for |
|---|---|---|
| Frontend | **Firebase Hosting** | Serving the chat web app |
| Backend/API | **Cloud Run** | Stateless API: `/survey`, `/chat`, `/user/{id}/status`, `/policies`, `/claims`, `/notifications` |
| Dev environment | **Cloud Shell / Cloud Shell Editor** | No local setup; git/python preinstalled |
| Agentic coding | **Antigravity 2.0 / Antigravity CLI (`agy`)** | Building and iterating on this codebase itself |
| Prompt prototyping | **AI Studio** | Fast iteration on GenAI prompts before wiring into the app |
| LLM — general reasoning | **Gemini** (Vertex AI / Agent Platform) | Intent routing, health/policy summaries, recommendation reasoning |
| LLM — clinical | **MedGemma** (Vertex AI Model Garden) | Any medical text/image interpretation task, if added |
| Structured data | **Cloud SQL** (Postgres) or **AlloyDB** | Users, policies, claims, health events, survey responses |
| Unstructured data | **Cloud Storage** | Policy PDFs, uploaded images (if MedGemma image use case is added) |
| Scheduled jobs | **Cloud Scheduler** | Daily checks: renewal dates, checkup gaps |
| Event delivery | **Pub/Sub** | Fan-out from Scheduler to the notification write path |
| Analytics | **BigQuery** | Event log: every interaction, recommendation shown, nudge sent |
| Dashboarding | **Looker** | Optional — engagement/impact chart for the demo |

All of the above are confirmed available in the provisioned `gcplab.me` sandbox; nothing here requires external accounts or billing outside the hackathon environment.

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

-- pre_survey_responses (New User path only)
CREATE TABLE pre_survey_responses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  age_bracket TEXT,
  has_existing_conditions BOOLEAN,
  has_current_insurance BOOLEAN,
  lifestyle_flags JSONB,        -- e.g. {"smoker": false, "exercise_freq": "weekly"}
  submitted_at TIMESTAMP DEFAULT now()
);

-- policies
CREATE TABLE policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  policy_type TEXT,             -- e.g. dental, health, life
  status TEXT,                  -- active, lapsed, pending
  coverage_summary TEXT,
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

-- health_events (self-reported or mock, feeds "health status" OPs)
CREATE TABLE health_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  event_type TEXT,              -- checkup, screening, vaccination
  event_date DATE,
  notes TEXT
);

-- notifications (Trigger/Action output, polled by Chat UI)
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  type TEXT,                    -- renewal_alarm, checkup_reminder, non_recommended_alert
  message TEXT,
  triggered_at TIMESTAMP DEFAULT now(),
  read BOOLEAN DEFAULT false
);

-- interaction_log (for BigQuery export / analytics)
CREATE TABLE interaction_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  ip_code TEXT,                 -- e.g. IP1, IP2...
  op_code TEXT,                 -- e.g. OP1, OP2...
  mechanism TEXT,                -- prompt | genai | recommender | trigger_action
  logged_at TIMESTAMP DEFAULT now()
);
```

Seed 3–5 fake users (mix of New and Existing) with realistic policy/claims/health data before building anything else — this unblocks every downstream feature without needing real integrations.

---

## 9. API surface (Cloud Run service)

| Endpoint | Method | Purpose |
|---|---|---|
| `POST /survey` | POST | Submit pre-survey answers for a new user |
| `POST /chat` | POST | Main entry point — body: `{user_id, message}`; router classifies user_type + IP, dispatches to the right mechanism, returns OP |
| `GET /user/{id}/status` | GET | Health status overview (OP1 both flows) |
| `GET /user/{id}/policies` | GET | List policies (OP2 existing flow, and policy catalog for new-user IP2) |
| `GET /user/{id}/claims` | GET | Claims history (IP4 existing flow) |
| `GET /user/{id}/notifications` | GET | Poll for alarms/reminders written by Trigger/Action |
| `POST /internal/trigger-check` | POST | Called by Cloud Scheduler daily — checks renewal dates and checkup gaps, writes to `notifications`, publishes to Pub/Sub |

### `/chat` request/response contract

```json
// Request
{ "user_id": "uuid", "message": "what policies do I have" }

// Response
{
  "ip_matched": "IP2",
  "user_type": "existing",
  "op_code": "OP2",
  "response_text": "You currently have 2 active policies...",
  "recommendations": [ { "policy_type": "dental", "reason": "no dental coverage on file" } ],
  "mechanism_used": "recommender"
}
```

---

## 10. GenAI prompt design (test these in AI Studio first)

**Intent classifier prompt** (feeds the router) — must return structured JSON:
```
System: You are an intent classifier for a health insurance assistant.
Classify the user's message into one of: IP1_pro_services, IP1_health_status,
IP2_all_policies, IP2_my_policies, IP3_pay_policies, IP4_my_claims.
Also state whether this fits a "new" or "existing" user flow.
Respond ONLY with JSON: {"ip": "...", "flow": "new|existing"}
```

**Health status summary prompt** (GenAI mechanism):
```
System: You are a friendly health assistant for Bupa. Given the user's
survey answers or health/claims history below, write a 3-4 sentence
plain-language health status overview. Avoid medical jargon. If data
suggests a preventive service gap, mention it briefly.
Data: {user_context_json}
```

**Recommendation reasoning prompt** (Recommendation Engine mechanism):
```
System: Given this user's current policies and claims history, identify:
(1) any preventive service gaps, (2) any policy type they don't have that
similar users typically do, (3) any existing policy that looks redundant
or non-recommended given their coverage. Return concise bullet points.
Data: {policies_json}, {claims_json}
```

Keep all three under version control as separate prompt files (`/prompts/*.md`) so they can be iterated independently of app code.

---

## 11. Build order (recommended sequence)

1. **Schema + seed data** — stand up Cloud SQL/AlloyDB, run the schema above, insert 3–5 fake users with varied data.
2. **Cloud Run API shell** — deploy a bare service with all endpoints stubbed (return mock JSON). Deploy early so something is always live to demo.
3. **Prompt prototyping in AI Studio** — nail the three prompts above before wiring them into code.
4. **Intent router** — wire the classifier prompt into `/chat`, returning `{ip, flow}` correctly for a handful of test messages.
5. **Wire the four mechanisms** — Prompt (pass-through), GenAI (Gemini call with user context), Recommender (rules + optional Gemini reasoning), Trigger/Action (Cloud Scheduler job hitting `/internal/trigger-check`).
6. **Pre-survey flow** — build `/survey`, store responses, confirm GenAI output changes when survey data is present vs absent.
7. **Chat UI** — simple web front end (Firebase Hosting) with a message pane, quick-reply buttons for the 6 IPs, and a notifications badge.
8. **End-to-end test both flows** — New User: survey → Pro-services intro → policy suggestions. Existing User: status → policies → claims → recommendations → trigger a reminder.
9. **Analytics (stretch)** — log every `/chat` call to `interaction_log`, export to BigQuery, build one Looker chart (e.g. "% of sessions where a preventive-service recommendation was shown").
10. **Demo polish** — script two short user journeys (one per segment) that map directly back to the three mission pillars (Teach / Explain / Aware).

---

## 12. Environment & tooling notes

- Log into `console.cloud.google.com` with the provided `@gcplab.me` credentials; the project is pre-assigned — select it from "Select a project."
- Same credentials work for **AI Studio** and **Antigravity**. For Antigravity, specify the project ID at login to get the Agent Platform (Business) plan — without it you'll default to Starter Quota; if you see "Starter Quota," log out and re-enter the project ID.
- Use **Cloud Shell** for all CLI work (git, python, gcloud preinstalled) — no local setup needed.
- Use **Antigravity CLI** (`agy` in Cloud Shell) or the Antigravity IDE for agent-assisted coding on this repo.
- **Do not** commit real API keys — this environment is decommissioned at the end of the event; keep secrets in Secret Manager or environment variables, not in code.
- Copy anything worth keeping to a persistent environment before the sandbox is torn down.

---

## 13. Suggested repo structure

```
bupa-ai-assistant/
├── api/                     # Cloud Run service
│   ├── main.py               # or index.js — routes above
│   ├── router.py             # intent classification logic
│   ├── mechanisms/
│   │   ├── prompt.py
│   │   ├── genai.py
│   │   ├── recommender.py
│   │   └── trigger_action.py
│   ├── db/
│   │   └── schema.sql        # section 8 above
│   └── requirements.txt
├── prompts/
│   ├── intent_classifier.md
│   ├── health_summary.md
│   └── recommendation.md
├── web/                      # Firebase Hosting front end
│   ├── index.html
│   ├── chat.js
│   └── survey.html
├── infra/
│   ├── scheduler-job.yaml    # Cloud Scheduler config for trigger checks
│   └── deploy.sh
└── README.md
```

---

## 14. Success criteria for the demo

- [ ] New user can complete the pre-survey and receive a personalized-feeling health overview and policy suggestions
- [ ] Existing user can ask about status, policies, and claims and get answers grounded in their actual seeded data
- [ ] At least one Trigger/Action nudge fires and appears in the UI (renewal alarm or checkup reminder)
- [ ] Recommendation Engine flags at least one coverage gap or non-recommended plan
- [ ] (Stretch) A BigQuery/Looker chart shows engagement across the demo users

This file is meant to be handed directly to an AI coding assistant (Antigravity, Claude Code, etc.) with an instruction like: *"Build this project following the spec in bupa-ai-assistant-build-spec.md, starting with section 11's build order."*
