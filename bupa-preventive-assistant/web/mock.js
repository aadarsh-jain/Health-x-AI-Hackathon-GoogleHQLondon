/* Offline UI/UX mock (spec §14 demo shapes). When APP_CONFIG.MOCK is true this
   monkey-patches window.fetch to answer the app's endpoints with representative
   in-browser data — so the whole UI can be exercised with NO backend running.
   Set APP_CONFIG.MOCK = false (config.js) to talk to the real API again. */
(function () {
  if (!window.APP_CONFIG || !window.APP_CONFIG.MOCK) return;
  const origFetch = window.fetch ? window.fetch.bind(window) : null;

  const GAPS = 5, USERS = 4;
  let actioned = 0;

  const REC = (service, reason, trigger_data, next_step, id) =>
    ({ id, service, reason, trigger_data, next_step });

  function recsFor(msg) {
    msg = (msg || "").toLowerCase();
    if (msg.includes("claim"))
      return [REC("Health Assessment",
        "Recommended because your last assessment was about 18 months ago.",
        { last_assessment_date: "2025-03-10", months_since: 18 },
        "Book your next health assessment", "r-ha")];
    if (msg.includes("policy") || msg.includes("cover"))
      return [REC("Policy review (non-recommended)",
        "You hold two overlapping comprehensive health policies with duplicate benefits; consolidating may avoid paying twice.",
        { overlapping_policies: ["cccc0003", "cccc0004"] },
        "Review overlapping cover", "r-pol")];
    if (msg.includes("stress") || msg.includes("sleep") || msg.includes("mental"))
      return [
        REC("Early Mental Health Support",
          "A few of your answers suggest early mental-health support could be worth exploring.",
          { wellbeing_flags: ["high_stress", "poor_sleep"] },
          "See mental-health support options", "r-mh"),
        REC("Personalised Health Programme",
          "Recommended because your reported activity level suggests a preventive fitness programme may help.",
          { lifestyle_flags: ["sedentary"] },
          "Explore the Personalised Health Programme", "r-php"),
      ];
    return [
      REC("Health Assessment",
        "Recommended because there is no health assessment on file.",
        { last_assessment_date: null, months_since: null },
        "Explore assessment availability", "r-ha0"),
      REC("Genomic Health",
        "Recommended because a family history of type 2 diabetes may warrant discussing screening with a clinician.",
        { condition: "type2_diabetes", relative: "father" },
        "Learn about Genomic Health", "r-gen"),
    ];
  }

  const NOTIFS = [
    { id: "n1", type: "assessment_due", service_family: "health_assessment",
      message: "Your last health assessment was 18 months ago - you may be due for another.", read: false },
    { id: "n2", type: "renewal_alarm", service_family: null,
      message: "Your health policy renews on 5 Oct 2026.", read: false },
    { id: "n3", type: "mh_checkin", service_family: "mental_health",
      message: "A quick wellbeing check-in might be worthwhile - support is available whenever you need it.", read: false },
  ];

  const DRAFT = {
    age: 52, height_cm: 178, weight_kg: 91, blood_type: "O+",
    family_history: { conditions: ["type2_diabetes"], notes: "father diagnosed at 58" },
    lifestyle: { activity_days: "1-2", tobacco: "former", diet: "fair" },
  };

  const json = (body) => new Response(JSON.stringify(body),
    { status: 200, headers: { "Content-Type": "application/json" } });

  window.fetch = function (url, opts) {
    opts = opts || {};
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const method = (opts.method || "GET").toUpperCase();
    let body = {};
    try { if (typeof opts.body === "string") body = JSON.parse(opts.body); } catch (_) {}

    if (path.endsWith("/impact/summary"))
      return Promise.resolve(json({ gaps_identified: GAPS, users_with_recommendations: USERS, recommendations_actioned: actioned }));
    if (path.endsWith("/notifications")) return Promise.resolve(json(NOTIFS));
    if (path.endsWith("/recommendations") && method === "GET") return Promise.resolve(json(recsFor("")));
    if (path.includes("/recommendations/") && path.endsWith("/action")) {
      actioned += 1;
      return Promise.resolve(json({ status: "actioned",
        impact: { gaps_identified: GAPS, users_with_recommendations: USERS, recommendations_actioned: actioned } }));
    }
    if (path.endsWith("/records-prefill"))
      return Promise.resolve(json({ source: "bupa_records", prefilled: true, survey_draft: DRAFT,
        confidence_note: "Pulled from your Bupa records - please review before submitting." }));
    if (path.endsWith("/reports/upload"))
      return Promise.resolve(json({ report_id: "mock-report", prefilled: true, extraction_status: "parsed",
        survey_draft: DRAFT, confidence_note: "Extracted from your uploaded report - please review.", model: "fallback" }));
    if (path.endsWith("/survey") && method === "POST") {
      const bmi = body.height_cm ? Math.round((body.weight_kg / ((body.height_cm / 100) ** 2)) * 10) / 10 : null;
      const hasSymptom = body.symptoms && body.symptoms.chief_complaint;
      const recs = recsFor(hasSymptom ? "" : "");
      if (hasSymptom) recs.push(REC("Digital GP",
        "Recommended because you reported a current symptom - a Digital GP can review it with you. This is not a diagnosis.",
        { chief_complaint: body.symptoms.chief_complaint }, "Book a Digital GP consultation", "r-gp"));
      return Promise.resolve(json({ op_code: "OP1", bmi, senior_mode_suggested: body.age >= 65,
        response_text: "Thanks for completing your check-in. One preventive step stands out: " + recs[0].service + ". " + recs[0].reason,
        recommendations: recs }));
    }
    if (path.endsWith("/chat") && method === "POST") {
      const recs = recsFor(body.message);
      return Promise.resolve(json({ ip_matched: "IP2", user_type: "existing", op_code: "OP2",
        response_text: "Here's where things stand. One preventive step stands out: " + recs[0].service + ". " + recs[0].reason,
        recommendations: recs, mechanism_used: "recommender" }));
    }
    return origFetch ? origFetch(url, opts) : Promise.resolve(json({}));
  };

  console.log("[mock] Offline UI mode active - no API calls leave the browser.");
})();
