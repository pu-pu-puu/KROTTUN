<!-- autopilot:start -->
# KROTTUN
Windows TUN proxy manager: Python, pywebview, sing-box, Wintun.

Verification: `python -m unittest discover -s tests` — 45 passed, including offline sing-box config check and host harness mocks. Earlier independent clean clone: 28 passed before host-harness additions.
`python -m core.kill_switch --help` exits 0; runtime imports verified. Existing dependencies used; clean installation unvalidated.
Launch: `python main.py` (unverified here; never launched because it changes real network settings).

## Autopilot
Run artifacts and requirements: `.autopilot/`. Resume with «продолжи автопилот».
Read `.autopilot/PROGRESS.md` when present and the current run before changes.
Only the user can remove a requirement. Never run live firewall/network changes during development without explicit authorization; use isolated verification.
Use scoped git history by file or requirement; do not read the entire history.
Protection survives stop, errors and exit; release must be explicit. Close GUI, then elevated project PowerShell: `python -m core.kill_switch --release` (mutates WFP; never run as a development check).
Read README recovery/limitations before network work. Isolated Windows VM packet capture is pending; tests do not prove leak prevention or release readiness.
Authorized host smoke: native 26-rule transaction creation/readback/abort succeeded; temporary deny-only policy blocked IPv4 TCP with 10013, cleanup and restored TCP passed. IPv6 unavailable. No TUN/proxy/packet-capture acceptance yet; see `.autopilot/host-validation.md` and `tools/host-validation/README.md`.
Native enumeration requires explicit layer GUIDs; zero layerKey fails with FWP_E_LAYER_NOT_FOUND. Preserve BOOTTIME/DISABLED enumeration.
Connection journal uses snapshots and can miss short-lived connections. See `.autopilot/PROGRESS.md` for unresolved acceptance work.
<!-- autopilot:end -->
