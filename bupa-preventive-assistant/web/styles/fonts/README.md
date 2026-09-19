# Fonts (self-hosted)

The app's active UI font is **Inter** — one common font used in **both** Normal and
Senior mode (only the size changes between modes, never the typeface).

- `Inter.woff2` ✓ active — a single **variable** font (latin subset, weight axis
  100–900), so 400/600/700 all come from one ~48 KB file. Referenced by
  `tokens.css` (`--font-sans: "Inter", system-ui, …`).

Self-hosted from Google Fonts (`fonts.gstatic.com`, Inter v20) — **no runtime CDN
call** (privacy / offline / CSP). Inter is licensed under the SIL Open Font License.

### Also present (not currently used)
- `AtkinsonHyperlegible-Regular.woff2`, `AtkinsonHyperlegible-Bold.woff2` — the
  Braille-Institute accessibility face the build spec (§18.1) originally locked.
  Kept on disk in case you want to switch back: set
  `--font-sans: "Atkinson Hyperlegible", …` and restore its `@font-face` blocks in
  `tokens.css`. **Note:** using Inter instead of Atkinson is a deliberate deviation
  from spec §18.1 (chosen for a more familiar/standard look).
