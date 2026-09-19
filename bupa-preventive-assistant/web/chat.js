/* Chat UI logic (spec §9 /chat, §16 impact, §5.2 recommendation cards). */
(function () {
  const API = window.APP_CONFIG.API_BASE;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // Small on-demand speaker button: click to hear this specific item read aloud
  // (works regardless of the global Read-aloud toggle). Returns null if unsupported.
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

  let userId = window.APP_CONFIG.DEMO_USERS[0].id;

  // ---- demo user picker ----
  const sel = $("userSelect");
  window.APP_CONFIG.DEMO_USERS.forEach((u) => {
    const o = document.createElement("option");
    o.value = u.id; o.textContent = u.label; sel.appendChild(o);
  });
  sel.addEventListener("change", () => { userId = sel.value; refresh(); });

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

  // ---- Senior Mode toggle (button optional) ----
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
      // Senior Mode turns read-aloud on by default (still independently toggleable).
      if (on && window.Voice.supported() && !window.Voice.isEnabled()) {
        window.Voice.setEnabled(true); syncVoice();
      }
    });
    syncToggle();
  }

  // ---- messaging ----
  function addMessage(text, who) {
    const el = document.createElement("div");
    el.className = "msg " + who;
    if (who === "bot") {
      const span = document.createElement("span");
      span.className = "msg-text";
      span.textContent = text;
      el.appendChild(span);
      const spk = makeSpeaker(text, "Listen to this message");
      if (spk) el.appendChild(spk);
    } else {
      el.textContent = text;
    }
    $("messages").appendChild(el);
    el.scrollIntoView({ block: "end" });
  }

  function addRecoCards(recs) {
    (recs || []).forEach((r) => {
      const card = document.createElement("article");
      card.className = "reco-card";
      const step = r.id
        ? `<button class="next-step tap" data-reco-id="${esc(r.id)}">→ ${esc(r.next_step)}</button>`
        : `<p class="next-step">→ ${esc(r.next_step)}</p>`;
      card.innerHTML =
        `<h3>${esc(r.service)}</h3>` +
        `<p class="reason">${esc(r.reason)}</p>` +
        `<div class="trigger"><span aria-hidden="true">🔎</span> Why: ` +
        `<code>${esc(JSON.stringify(r.trigger_data))}</code></div>` +
        step;
      const spk = makeSpeaker(`${r.service}. ${r.reason} Next step: ${r.next_step}.`,
                              "Listen to this recommendation");
      if (spk) { spk.classList.add("speaker-card"); card.appendChild(spk); }
      $("messages").appendChild(card);
    });
  }

  // Tapping a recommendation's next step marks it actioned -> impact counter ticks (§16)
  $("messages").addEventListener("click", async (e) => {
    const btn = e.target.closest("button.next-step[data-reco-id]");
    if (!btn || btn.disabled) return;
    try {
      await fetch(`${API}/recommendations/${btn.dataset.recoId}/action`, { method: "POST" });
      btn.disabled = true;
      btn.textContent = "✓ Added to your plan";
      refresh();
    } catch (_) { /* API down; leave the button as-is */ }
  });

  async function send(message) {
    if (!message) return;
    addMessage(message, "user");
    try {
      const res = await fetch(API + "/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, message })
      });
      const data = await res.json();
      addMessage(data.response_text || "…", "bot");
      addRecoCards(data.recommendations);
      refresh();
    } catch (e) {
      addMessage("Sorry — I couldn't reach the assistant. Is the API running?", "bot");
    }
  }

  $("chatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const val = $("chatInput").value.trim();
    $("chatInput").value = "";
    send(val);
  });

  // ---- Voice input (speech-to-text) via the browser's SpeechRecognition ----
  const micBtn = $("micBtn");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const PLACEHOLDER = "Ask about your health or cover…";
  if (micBtn) {
    if (!SR) {
      micBtn.disabled = true;
      micBtn.title = "Voice input isn't supported in this browser";
    } else {
      const rec = new SR();
      rec.lang = "en-GB";
      rec.interimResults = true;
      rec.continuous = false;
      let listening = false;
      let gotFinal = false;
      let cancelled = false;

      rec.onstart = () => {
        listening = true;
        gotFinal = false;
        cancelled = false;
        micBtn.classList.add("listening");
        micBtn.setAttribute("aria-pressed", "true");
        $("chatInput").placeholder = "Listening… speak now";
      };
      rec.onend = () => {
        listening = false;
        micBtn.classList.remove("listening");
        micBtn.setAttribute("aria-pressed", "false");
        $("chatInput").placeholder = PLACEHOLDER;
        const text = $("chatInput").value.trim();
        // Auto-send once dictation produced a final transcript (unless cancelled).
        if (gotFinal && text && !cancelled) {
          $("chatInput").value = "";
          send(text);
        } else {
          $("chatInput").focus();   // nothing final captured -> let the user edit/send
        }
      };
      rec.onerror = (e) => {
        $("chatInput").placeholder =
          e.error === "not-allowed" ? "Microphone blocked — allow it in the browser." : PLACEHOLDER;
      };
      rec.onresult = (e) => {
        let text = "";
        for (let i = 0; i < e.results.length; i++) {
          text += e.results[i][0].transcript;
          if (e.results[i].isFinal) gotFinal = true;
        }
        $("chatInput").value = text;
      };

      micBtn.addEventListener("click", () => {
        if (listening) { cancelled = true; rec.stop(); return; }  // click again = cancel (no send)
        $("chatInput").value = "";
        try { rec.start(); } catch (_) { /* already starting */ }
      });
    }
  }
  $("quickReplies").addEventListener("click", (e) => {
    if (e.target.matches("button")) send(e.target.dataset.msg);
  });

  // ---- notifications + impact ----
  async function loadNotifications() {
    try {
      const res = await fetch(`${API}/user/${userId}/notifications`);
      const items = await res.json();
      const unread = items.filter((n) => !n.read).length;
      $("notifBadge").textContent = unread;
      const wrap = $("notifs");
      wrap.innerHTML = "";
      items.forEach((n) => {
        const div = document.createElement("div");
        div.className = "notif";
        div.innerHTML =
          `<span class="icon" aria-hidden="true">🔔</span>` +
          `<div><strong>${esc(n.type)}</strong><br>${esc(n.message)}</div>`;
        const spk = makeSpeaker(n.message, "Listen to this reminder");
        if (spk) { spk.classList.add("speaker-card"); div.appendChild(spk); }
        wrap.appendChild(div);
      });
    } catch (e) { /* API may be down; leave as-is */ }
  }

  async function loadImpact() {
    try {
      const res = await fetch(`${API}/impact/summary`);
      const d = await res.json();
      $("gaps").textContent = d.gaps_identified ?? 0;
      $("recos").textContent = d.users_with_recommendations ?? 0;
      $("actioned").textContent = d.recommendations_actioned ?? 0;
    } catch (e) { /* ignore */ }
  }

  function refresh() { loadNotifications(); loadImpact(); }

  // initial paint
  addMessage("Hi! I can help you discover the right preventive services at the right time. Try a quick reply below.", "bot");
  refresh();
})();
