# Diagnostic placement options

Open index.html for three standalone, interactive 520×760 mock screens:

- A: header utility beside external IP, available from every tab.
- B: action beside Connected / Disconnected on the home screen.
- C: independent utility row beneath the selected server card.

Only radio-circle pixel alignment is applied to production. Diagnostic placement
remains unchanged until the user chooses. Existing visual identity, map, background,
window geometry and backend contracts are preserved. Mock IPs use documentation
ranges; diagnostic responses are explicitly demonstrations. Flags are inline SVG
so the prototypes do not need external requests or the Python bridge.

Rebuild with `node prototypes/diagnostic-placement/build.cjs`.
Verification: `node prototypes/diagnostic-placement/verify.cjs`,
`node prototypes/diagnostic-placement/render.cjs` and existing
`node prototypes/ping-controls/verify.cjs` all PASS on 2026-10-25.
Dot test reproduced fractional pixel edges before CSS correction (32.5 != 33),
then passed active/selected, 480/520 widths and 1/1.25/1.5/2 density.
Prototype verification covers button visibility, viewport containment, diagnostic
modal open/close, A on Servers, and absence of browser console errors.

Impeccable detector ran once. Its observations concern incumbent toggle/toast
easing, background dots and tab glow; these are outside this scoped adjustment
and the user's existing visual direction was retained. No new detector warnings
were attributed to the changed controls.

EXE was not rebuilt and the native application/network settings were not touched.

## Approved C applied

The user selected C. Production now places the full-width diagnostic utility as
a sibling after the server card, with the approved icon, subtitle and chevron.
The existing btnDiagnostics/openDiagnostics handler is preserved. Dot alignment
correction remains included. `verify-production.cjs` passes 480/520px,
protected/unarmed, viewport containment and keyboard activation of the existing
diagnostics modal. Production screenshots: production-c-480.png/production-c-520.png.

## Requested EXE

2026-10-25: `dist/diagnostic-c/KROTTUN.exe`, version 2.6.0, 44,142,298 bytes.
PyInstaller exit 0. SHA256:
`1f0eca9f3015c83b31b1e14b235f10a032da0a8b914bd9e572067d4bc0b1ceef`.
Archive verifier PASS: production HTML and embedded binaries match source,
corrected Python modules/main match source bytecode, multiprocessing hook and
requireAdministrator manifest present. EXE was not launched.
