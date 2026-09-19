/* Survey + report-upload logic (spec §4.5, §9 /reports/upload + /survey).
   Full Appendix A checklist: Section 1 mandatory; Sections 2–5 optional and
   serialised into family_history / lifestyle / medications_allergies / symptoms. */
(function () {
  const API = window.APP_CONFIG.API_BASE;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const val = (id) => ($(id) ? $(id).value.trim() : "");
  const checked = (name) =>
    Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map((e) => e.value);
  const radio = (name) => {
    const el = document.querySelector(`input[name="${name}"]:checked`);
    return el ? el.value : "";
  };

  // On-demand speaker button (same behaviour as the assistant page).
  function makeSpeaker(text, label) {
    if (!window.Voice || !window.Voice.supported()) return null;
    const b = document.createElement("button");
    b.type = "button";
    b.className = "speaker";
    b.textContent = "🔊";
    b.title = label || "Listen";
    b.setAttribute("aria-label", label || "Listen");
    b.addEventListener("click", (e) => { e.stopPropagation(); window.Voice.say(text); });
    return b;
  }

  const userId = window.APP_CONFIG.DEMO_USERS[0].id;
  let reportId = null;

  // ---- Voice (read-aloud) toggle ----
  const vt = $("voiceToggle");
  const syncVoice = () => {
    if (!vt) return;
    const on = window.Voice.isEnabled();
    vt.setAttribute("aria-pressed", on ? "true" : "false");
    vt.textContent = on ? "🔊 Voice: On" : "🔊 Read aloud";
  };
  if (vt) {
    if (!window.Voice.supported()) { vt.disabled = true; vt.title = "Voice not supported in this browser"; }
    vt.addEventListener("click", () => { window.Voice.toggle(); syncVoice(); });
    syncVoice();
  }

  // ---- Senior toggle (button optional) ----
  const st = $("seniorToggle");
  const syncToggle = () => {
    if (!st) return;
    const on = document.documentElement.classList.contains("senior");
    st.setAttribute("aria-pressed", on ? "true" : "false");
    st.textContent = on ? "Senior Mode: On" : "Senior Mode";
  };
  if (st) {
    st.addEventListener("click", () => {
      const on = window.SeniorMode.toggle();
      syncToggle();
      if (on && window.Voice.supported() && !window.Voice.isEnabled()) {
        window.Voice.setEnabled(true); syncVoice();
      }
    });
    syncToggle();
  }

  // ---- input-method areas (§4.5: upload / bupa_records / manual) ----
  document.querySelectorAll('input[name="method"]').forEach((r) =>
    r.addEventListener("change", () => {
      const method = document.querySelector('input[name="method"]:checked').value;
      $("uploadArea").style.display = method === "upload" ? "" : "none";
      $("recordsArea").style.display = method === "bupa_records" ? "" : "none";
    }));

  // ---- conditional controls ----
  // cancer detail appears when the "cancer" family-history box is ticked
  document.querySelectorAll('input[name="famhist"]').forEach((c) =>
    c.addEventListener("change", () => {
      const on = document.querySelector('input[name="famhist"][value="cancer"]').checked;
      $("cancerDetailField").hidden = !on;
    }));

  // medications rows appear when "Yes" is chosen
  function addMedRow(med) {
    med = med || {};
    const row = document.createElement("div");
    row.className = "med-row";
    row.innerHTML =
      `<input class="med-name"   type="text" placeholder="Name" value="${esc(med.name)}" />` +
      `<input class="med-dose"   type="text" placeholder="Dosage" value="${esc(med.dosage)}" />` +
      `<input class="med-freq"   type="text" placeholder="Frequency" value="${esc(med.frequency)}" />` +
      `<input class="med-reason" type="text" placeholder="Reason" value="${esc(med.reason)}" />`;
    $("medsRows").appendChild(row);
  }
  document.querySelectorAll('input[name="takesMeds"]').forEach((r) =>
    r.addEventListener("change", () => {
      const yes = radio("takesMeds") === "yes";
      $("medsArea").hidden = !yes;
      if (yes && !$("medsRows").children.length) addMedRow();
    }));
  $("addMed").addEventListener("click", () => addMedRow());

  // severity slider live value
  $("severity").addEventListener("input", () => { $("severityOut").textContent = $("severity").value; });

  // ---- pre-fill helpers ----
  function markPrefilled(forId) {
    const tag = document.querySelector(`.prefilled-tag[data-for="${forId}"]`);
    if (tag) tag.hidden = false;
  }
  function setSelect(id, value) { if (value && $(id)) $(id).value = value; }
  function tickAll(name, values) {
    (values || []).forEach((v) => {
      const el = document.querySelector(`input[name="${name}"][value="${v}"]`);
      if (el) el.checked = true;
    });
  }

  // Apply a survey_draft dict (from MedGemma upload OR Bupa records) to the form.
  function applyDraft(d) {
    d = d || {};
    if (d.age) { $("age").value = d.age; markPrefilled("age"); }
    if (d.height_cm) { $("height").value = d.height_cm; markPrefilled("height"); }
    if (d.weight_kg) { $("weight").value = d.weight_kg; markPrefilled("weight"); }
    if (d.blood_type) { $("blood").value = String(d.blood_type).toUpperCase(); markPrefilled("blood"); }
    if (d.ethnicity) { setSelect("ethnicity", d.ethnicity); markPrefilled("ethnicity"); }

    const fh = d.family_history || {};
    if (fh.conditions && fh.conditions.length) { tickAll("famhist", fh.conditions); markPrefilled("family"); }
    if (fh.notes) { $("famNotes").value = fh.notes; markPrefilled("family"); }
    if (document.querySelector('input[name="famhist"][value="cancer"]').checked) $("cancerDetailField").hidden = false;

    const l = d.lifestyle || {};
    setSelect("activity", l.activity_days); setSelect("activityMin", l.activity_minutes);
    setSelect("diet", l.diet); setSelect("fruitveg", l.fruit_veg);
    if (l.water_glasses) $("water").value = l.water_glasses;
    tickAll("dietpat", l.dietary_pattern);
    setSelect("sleep", l.sleep_hours); setSelect("stress", l.stress);
    setSelect("tobacco", l.tobacco); setSelect("alcohol", l.alcohol);

    const ma = d.medications_allergies || {};
    tickAll("allergy", ma.allergies);
    if (ma.allergy_details) $("allergyDetails").value = ma.allergy_details;
    if (ma.medications && ma.medications.length) {
      document.querySelector('input[name="takesMeds"][value="yes"]').checked = true;
      $("medsArea").hidden = false;
      $("medsRows").innerHTML = "";
      ma.medications.forEach(addMedRow);
    }

    const s = d.symptoms || {};
    if (s.chief_complaint) $("chief").value = s.chief_complaint;
    setSelect("onset", s.onset); setSelect("timing", s.timing);
    if (s.severity != null) { $("severity").value = s.severity; $("severityOut").textContent = s.severity; }
    if (s.better) $("better").value = s.better;
    if (s.worse) $("worse").value = s.worse;
  }

  // ---- upload -> MedGemma pre-fill ----
  $("reportFile").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    $("uploadStatus").textContent = "Reading your report with MedGemma…";
    const fd = new FormData();
    fd.append("user_id", userId);
    fd.append("file", file);
    try {
      const res = await fetch(API + "/reports/upload", { method: "POST", body: fd });
      const data = await res.json();
      reportId = data.report_id;
      applyDraft(data.survey_draft);
      $("uploadStatus").textContent = data.prefilled
        ? "✓ We pre-filled what we could. Please review and correct anything before submitting."
        : "We couldn't read that file — please fill the form manually.";
    } catch (err) {
      $("uploadStatus").textContent = "Upload failed — is the API running? You can still fill the form manually.";
    }
  });

  // ---- select from Bupa records -> pre-fill (no upload) ----
  $("pullRecords").addEventListener("click", async () => {
    $("recordsStatus").textContent = "Fetching your Bupa records…";
    try {
      const res = await fetch(`${API}/user/${userId}/records-prefill`);
      const data = await res.json();
      applyDraft(data.survey_draft);
      $("recordsStatus").textContent = data.prefilled
        ? "✓ Pre-filled from your Bupa records. Please review and correct anything before submitting."
        : "We couldn't find records to pre-fill — please fill the form manually.";
    } catch (err) {
      $("recordsStatus").textContent = "Couldn't reach your records — is the API running? You can still fill the form manually.";
    }
  });

  // ---- collect the full Appendix A payload ----
  function collectMedications() {
    if (radio("takesMeds") !== "yes") return [];
    return Array.from(document.querySelectorAll(".med-row")).map((row) => ({
      name: row.querySelector(".med-name").value.trim(),
      dosage: row.querySelector(".med-dose").value.trim(),
      frequency: row.querySelector(".med-freq").value.trim(),
      reason: row.querySelector(".med-reason").value.trim(),
    })).filter((m) => m.name);
  }

  function buildPayload() {
    const conditions = checked("famhist").filter((v) => !["none", "unknown"].includes(v));
    const stress = val("stress");
    const sleep = val("sleep");
    const poorSleep = sleep === "<5" || sleep === "5-6";
    return {
      user_id: userId,
      age: Number(val("age")),
      height_cm: Number(val("height")),
      weight_kg: Number(val("weight")),
      blood_type: val("blood"),
      ethnicity: val("ethnicity") || null,
      family_history: {
        conditions,
        cancer_detail: val("cancerDetail") || null,
        notes: val("famNotes") || null,
      },
      lifestyle: {
        activity_days: val("activity"), activity_minutes: val("activityMin"),
        diet: val("diet"), fruit_veg: val("fruitveg"),
        water_glasses: val("water") ? Number(val("water")) : null,
        dietary_pattern: checked("dietpat"),
        sleep_hours: sleep, stress, tobacco: val("tobacco"), alcohol: val("alcohol"),
      },
      medications_allergies: {
        allergies: checked("allergy"),
        allergy_details: val("allergyDetails") || null,
        medications: collectMedications(),
      },
      symptoms: {
        chief_complaint: val("chief") || null,
        onset: val("onset"), timing: val("timing"),
        severity: Number(val("severity")),
        better: val("better") || null, worse: val("worse") || null,
      },
      // derived shortcut feeding the mental-health path (spec §8)
      wellbeing_flags: { stress, sleep: poorSleep ? "poor" : "ok" },
      report_id: reportId,
    };
  }

  // ---- submit survey ----
  $("surveyForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = buildPayload();
    try {
      const res = await fetch(API + "/survey", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (!res.ok) { alert("Please complete the required fields (age, height, weight, blood type)."); return; }
      const data = await res.json();
      if (data.senior_mode_suggested) {
        window.SeniorMode.enable(); syncToggle();
        if (window.Voice.supported() && !window.Voice.isEnabled()) { window.Voice.setEnabled(true); syncVoice(); }
      }
      $("result").hidden = false;
      $("resultText").innerHTML = `<p>${esc(data.response_text)}</p>` +
        (data.bmi ? `<p class="hint">Your BMI is ${esc(data.bmi)}.</p>` : "");
      const overviewSpk = makeSpeaker(data.response_text, "Listen to your overview");
      if (overviewSpk) $("resultText").appendChild(overviewSpk);

      const cards = $("resultCards");
      cards.innerHTML = "";
      (data.recommendations || []).forEach((r) => {
        const card = document.createElement("article");
        card.className = "reco-card";
        card.innerHTML =
          `<h3>${esc(r.service)}</h3>` +
          `<p class="reason">${esc(r.reason)}</p>` +
          `<div class="trigger"><span aria-hidden="true">🔎</span> Why: <code>${esc(JSON.stringify(r.trigger_data))}</code></div>` +
          `<p class="next-step">→ ${esc(r.next_step)}</p>`;
        const spk = makeSpeaker(`${r.service}. ${r.reason} Next step: ${r.next_step}.`,
                                "Listen to this recommendation");
        if (spk) { spk.classList.add("speaker-card"); card.appendChild(spk); }
        cards.appendChild(card);
      });
      $("result").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      alert("Couldn't submit — is the API running?");
    }
  });

  // ---- Voice input (speech-to-text) on the open-text survey fields ----
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let activeMic = null;   // { el, btn }
  const rec = SR ? new SR() : null;
  if (rec) {
    rec.lang = "en-GB";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e) => {
      if (!activeMic) return;
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      activeMic.el.value = text;
    };
    rec.onend = () => {
      if (activeMic) {
        activeMic.btn.classList.remove("listening");
        activeMic.btn.setAttribute("aria-pressed", "false");
        activeMic.el.focus();
      }
      activeMic = null;
    };
    rec.onerror = () => { if (activeMic) activeMic.btn.classList.remove("listening"); };
  }

  function attachMic(id) {
    const input = document.getElementById(id);
    if (!input || !SR) return;   // no button if the field is missing or unsupported
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mic mic-inline";
    btn.textContent = "🎤";
    btn.title = "Speak this answer";
    btn.setAttribute("aria-label", "Speak this answer");
    btn.setAttribute("aria-pressed", "false");
    const row = document.createElement("div");
    row.className = "input-mic";
    input.parentNode.insertBefore(row, input);
    row.appendChild(input);
    row.appendChild(btn);
    btn.addEventListener("click", () => {
      if (activeMic && activeMic.el === input) { rec.stop(); return; }
      if (activeMic) rec.stop();
      activeMic = { el: input, btn };
      input.value = "";
      btn.classList.add("listening");
      btn.setAttribute("aria-pressed", "true");
      try { rec.start(); } catch (_) { /* already starting */ }
    });
  }

  ["famNotes", "cancerDetail", "allergyDetails", "chief", "better", "worse"].forEach(attachMic);
})();
