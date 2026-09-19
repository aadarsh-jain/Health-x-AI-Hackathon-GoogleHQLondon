// Front-end config. Set API_BASE to your deployed Cloud Run URL.
// For local dev against a local API: "http://localhost:8080".
window.APP_CONFIG = {
  API_BASE: "http://127.0.0.1:8123",
  // Offline UI/UX mode: true = mock.js serves all data in-browser (no backend).
  // Set to false to talk to the real API at API_BASE.
  MOCK: false,
  // Demo users from seed.sql (spec §8). Handy for the demo dropdown.
  DEMO_USERS: [
    { id: "11111111-1111-1111-1111-111111111111", label: "Ravi (new, uploaded report, 52)" },
    { id: "55555555-5555-5555-5555-555555555555", label: "Joan (new, manual, 70 — Senior)" },
    { id: "22222222-2222-2222-2222-222222222222", label: "Margaret (existing, 68)" },
    { id: "33333333-3333-3333-3333-333333333333", label: "Sam (existing, 34)" },
    { id: "44444444-4444-4444-4444-444444444444", label: "Priya (existing, 45)" }
  ]
};

// Senior Mode toggle (spec §18) — persists across pages.
window.SeniorMode = {
  apply() {
    const on = localStorage.getItem("seniorMode") === "1";
    document.documentElement.classList.toggle("senior", on);
    return on;
  },
  toggle() {
    const on = localStorage.getItem("seniorMode") !== "1";
    localStorage.setItem("seniorMode", on ? "1" : "0");
    this.apply();
    return on;
  },
  enable() { localStorage.setItem("seniorMode", "1"); this.apply(); }
};
window.SeniorMode.apply();
