# Diagnostics with a disconnected tunnel — proposals

Awaiting user selection. Production diagnostics/backend and EXE are unchanged.

A: reason banner plus familiar condensed result list.
B: dedicated blocked state with one summary of checks that never ran.
C: state ledger plus expandable skipped-check details.

Blocked and unknown are separate demo scenarios; unknown never claims blocking.
Windows proxy is explicitly a separate local setting, not an egress verdict.
The primary action closes the dialog and navigates home only. It never connects,
releases protection, changes the OS or performs a transport request.

For eventual implementation, blocked wording must come from a valid lifecycle
context with a disconnected tunnel and confirmed protection state. Do not infer
blocking from skipped results, a failed connectivity test, or mode=None. Unknown,
unarmed-without-selected-proxy, cancellation, timeout and real diagnostics remain
distinct cases. Preserve diagnostic child ownership and release barriers.

Build: node prototypes/diagnostic-blocked/build.cjs
Verify: node prototypes/diagnostic-blocked/verify.cjs
2026-10-25: PASS A/B/C at 480/520, unknown vs confirmed wording, modal bounds,
keyboard navigation/details, home-only action, reopen and gallery scenario control.
Every external request was aborted during rendering. Visual inspection passed.
Mechanical detector observations concern inherited background/glow/easing; the
scoped modal variants preserve the established visual identity.

## Approved A — production integration

Backend snapshots now include availability_reason only for a completed, valid
context. A disconnected core and ProtectionSession's confirmed blocked state
yield protection_blocked. Unknown protection, no selected unarmed proxy, and
transitions have separate reasons. Stale or cancelled results cannot retain the
blocking claim. No new native calls or policy mutations were introduced.

The modal shows the approved banner and compact rows only for four skipped
network checks with an explicit reason. Normal runs, cancellation, RPC errors and
reopening reset the compact layout. Windows proxy retains pass/warning/unknown
semantics. Home action only closes/navigates (Servers for no selected proxy).
Production screenshots: production-a-480.png, production-a-520.png.

2026-10-25: backend diagnostics tests and production browser verifier PASS.
Existing proxy-controls verifier (real diagnostics progress/cancel/reopen/stale/
RPC-error/timeout, edit/fallback/XSS/map invariants) and Info passport verifier PASS.
Independent read-only review found no substantive issues. EXE not rebuilt.
