/* Read-aloud voice option (spec §18 accessibility — helps older adults).
   Uses the browser's built-in SpeechSynthesis (Web Speech API) — no network,
   no third-party service. Toggleable and persisted; slightly slower rate in
   Senior Mode for clarity. Speaks the assistant's plain-language replies. */
window.Voice = (function () {
  const KEY = "voiceEnabled";
  const synth = window.speechSynthesis || null;
  let enabled = localStorage.getItem(KEY) === "1";

  function supported() { return !!synth; }
  function isEnabled() { return enabled && supported(); }

  function setEnabled(v) {
    enabled = !!v;
    localStorage.setItem(KEY, enabled ? "1" : "0");
    if (!enabled && synth) synth.cancel();
    return isEnabled();
  }
  function toggle() { return setEnabled(!enabled); }

  function speak(text) {
    if (!isEnabled() || !text) return;
    try {
      synth.cancel(); // don't stack utterances
      const u = new SpeechSynthesisUtterance(String(text));
      u.lang = "en-GB";
      u.rate = document.documentElement.classList.contains("senior") ? 0.9 : 0.95;
      u.pitch = 1; u.volume = 1;
      synth.speak(u);
    } catch (_) { /* ignore speech errors */ }
  }

  function stop() { if (synth) synth.cancel(); }

  // On-demand read-aloud for a per-item speaker button. Ignores the global
  // toggle (an explicit click is an explicit request). Click again while it's
  // speaking THIS text to stop it (toggle).
  let lastText = null;
  function say(text) {
    if (!supported() || !text) return;
    const same = synth.speaking && lastText === String(text);
    synth.cancel();
    if (same) { lastText = null; return; }  // was reading this -> stop
    try {
      const u = new SpeechSynthesisUtterance(String(text));
      u.lang = "en-GB";
      u.rate = document.documentElement.classList.contains("senior") ? 0.9 : 0.95;
      u.pitch = 1; u.volume = 1;
      u.onend = () => { lastText = null; };
      lastText = String(text);
      synth.speak(u);
    } catch (_) { /* ignore */ }
  }

  return { supported, isEnabled, setEnabled, toggle, speak, say, stop };
})();
