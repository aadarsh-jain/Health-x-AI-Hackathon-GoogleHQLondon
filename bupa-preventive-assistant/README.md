# Bupa Preventive Health Assistant

An AI-powered concierge that helps people **discover, understand and engage** with
Bupa's preventive health services at the right time — built for the Health × AI
Hackathon (Adeline Sprint, London, powered by Google MedGemma).

Full design brief: `../bupa-ai-assistant-build-spec-v3.md`.

**Hero feature — Preventive Gap Detection**: identify what preventive care you may
be missing, explain *why* (a transparent reasoning trail), and help you act — before
you become unwell.

---

## Architecture at a glance

```
Chat UI (Firebase Hosting)  ─▶  Cloud Run API (FastAPI)
                                   │
                                   ├─ router      intent (Gemini | fallback)
                                   ├─ GenAI pipeline (safety-critical, §5.1):
                                   │     MedGemma → guardrail(code) → recommender → Gemini
                                   ├─ recommender  Preventive Gap Detector (transparent objects)
                                   └─ trigger/action  Cloud Scheduler + Pub/Sub nudges
                                   │
                                   ▼
                     Cloud SQL/AlloyDB · Cloud Storage · BigQuery
```

**Safety pipeline**: MedGemma output *never* reaches the user directly. A
deterministic guardrail (`api/mechanisms/guardrail.py`) drops off-list or
low-confidence signals and rewrites any diagnostic phrasing into preventive
framing ("may warrant discussing X with a clinician"). Even the final Gemini text
is passed through `sanitize()` before display.

**Runs without the cloud models**: every Vertex AI call has a deterministic
fallback (`api/vertex.py`), so the full pipeline and demo work even if MedGemma
quota is flaky. Flip `USE_VERTEX=true` to go live.

---

## Repo layout

```
api/            FastAPI service (Cloud Run)
  main.py         all endpoints (§9)
  router.py       intent classification
  vertex.py       Gemini + MedGemma wrappers w/ fallback
  db.py, config.py
  mechanisms/     prompt · genai · guardrail · recommender · trigger_action
  db/             schema.sql + seed.sql (5 demo users + services catalog)
prompts/        the 6 versioned prompts (incl. guardrail_rules.md)
web/            Firebase Hosting front end (accessible, §18; Senior Mode)
infra/          scheduler-job.yaml + deploy.sh
```

---

## Configuration (do this first)

Real config files are **git-ignored** — copy the committed `*.example` templates
and edit them (they never get committed, so no secrets/URLs leak to git):

```bash
cp .env.example .env                       # API env vars (api/config.py reads these)
cp web/config.example.js web/config.js     # front-end API_BASE + MOCK flag
```
- `.env` — `DATABASE_URL`, `USE_VERTEX`, `GCP_PROJECT`, `MEDGEMMA_ENDPOINT`, … (see the file).
- `web/config.js` — set `API_BASE`; leave `MOCK: true` to run the UI with no backend, or
  `false` to hit the real API.

Ignored by git: `.env`, `web/config.js`, `*.db` (local SQLite), and any GCP key
(`*-key.json`, `credentials.json`, `*.pem`). Committed: the `*.example` templates.

## Quick start

### 1. Database (Cloud SQL / AlloyDB, or local Postgres)
```bash
psql "$DATABASE_URL" -f api/db/schema.sql
psql "$DATABASE_URL" -f api/db/seed.sql
```

### 2. API (local)
```bash
cd api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://user:pass@localhost:5432/bupa"
export USE_VERTEX=false          # true + GCP_PROJECT + MEDGEMMA_ENDPOINT to go live
uvicorn main:app --reload --port 8080
```
Open http://localhost:8080/ — you should see `{"service": "...", "vertex": false}`.

### 3. Front end (local)
Set `API_BASE` in `web/config.js` to `http://localhost:8080`, then serve `web/`:
```bash
cd web && python -m http.server 5000
```
Open http://localhost:5000/ (chat) and `/survey.html` (survey + upload).

### 4. Deploy to the sandbox
```bash
bash infra/deploy.sh          # Cloud Run + Storage + Pub/Sub + Scheduler
# then set web/config.js API_BASE to the printed URL and: firebase deploy --only hosting
```

---

## Demo script (2 minutes — spec §15)

1. **Survey → Upload a report** (a `.txt` with `Age: 52 / Height: 178 / Weight: 91 /
   Blood type: O+ / family history diabetes`). MedGemma pre-fills; edit one field
   live to show it's reviewable.
2. **Submit** → the safety pipeline runs → gap cards appear with all four
   transparency fields and guarded phrasing.
3. **Assistant page** → a proactive reminder is in the Reminders panel; the impact
   counters show non-zero. Tap a recommendation's **next-step button** → the
   "actioned" counter ticks up live (§16). Toggle **Senior Mode** to show the tier.
4. **Existing user** (pick Margaret/Priya) → ask about claims/policies; show the
   overdue-assessment recommendation and the redundant-policy alert. On a new
   check-in, the **"Select from your Bupa records"** option pre-fills the form
   from stored history — no upload needed (§4.5).

### Demo endpoints (curl)
```bash
curl localhost:8080/impact/summary
curl localhost:8080/user/22222222-2222-2222-2222-222222222222/recommendations
curl localhost:8080/user/22222222-2222-2222-2222-222222222222/records-prefill
curl -X POST localhost:8080/chat -H 'Content-Type: application/json' \
  -d '{"user_id":"33333333-3333-3333-3333-333333333333","message":"I feel stressed and cant sleep"}'
# mark a recommendation actioned -> the live impact counter moves (§16)
curl -X POST localhost:8080/recommendations/99990003-0000-0000-0000-000000000003/action
curl -X POST localhost:8080/internal/trigger-check
```

---

## Accessibility (spec §18)

Two-tier typography: an accessible **Adult baseline** (18px body, 1.5 line-height,
≥4.5:1 contrast, 44px targets) and a **Senior tier** (22px, 1.65, ≥7:1, 52px) toggled
by one `html.senior` class — auto-offered when survey `age ≥ 65`. Font: **Atkinson
Hyperlegible** (OFL), self-hosted in `web/styles/fonts/` — no runtime CDN call.

## Tests
```bash
cd api
python -m pytest -q                 # fast: pipeline/guardrail unit tests
DATABASE_URL=postgresql://… python -m pytest -q   # + e2e over both flows (needs seeded DB)
```
`test_pipeline.py` runs with no deps beyond the app; `test_e2e.py` exercises the
real API (upload → survey → gaps; existing status/policies/claims; guardrail;
trigger nudges; live impact counter) and self-skips unless `DATABASE_URL` is set.

## Not production
Hackathon MVP with seeded fake data. See spec §17 for the auth + compliance work
required before any real user data. MedGemma output is informational, not diagnosis.
