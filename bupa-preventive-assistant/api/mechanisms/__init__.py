"""The four AI mechanisms (spec §5).

1. prompt          — parse raw intent (no model call)
2. genai           — the safety pipeline: MedGemma -> guardrail -> Gemini
3. recommender     — Preventive Gap Detector (transparent recommendations)
4. trigger_action  — timed nudges (Cloud Scheduler + Pub/Sub)
"""
