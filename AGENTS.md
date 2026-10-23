<!-- autopilot:start -->
# KROTTUN
Windows TUN proxy manager: Python, pywebview, sing-box, Wintun.

Verification: `python -m unittest discover -s tests` — 83 passed, including offline sing-box config check and host harness mocks. Earlier independent clean clone: 28 passed before host-harness additions.
`python -m core.kill_switch --help` exits 0; runtime imports verified. Existing dependencies used; clean installation unvalidated.
Launch: `python main.py` (unverified here; never launched because it changes real network settings).

## Autopilot
Run artifacts and requirements: `.autopilot/`. Resume with «продолжи автопилот».
Read `.autopilot/PROGRESS.md` when present and the current run before changes.
Only the user can remove a requirement. Never run live firewall/network changes during development without explicit authorization; use isolated verification.
Use scoped git history by file or requirement; do not read the entire history.
Protection survives stop, errors and exit; release must be explicit. Close GUI, then elevated project PowerShell: `python -m core.kill_switch --release` (mutates WFP; never run as a development check).
Read README recovery/limitations before network work. Isolated Windows VM packet capture is pending; tests do not prove leak prevention or release readiness.
Authorized host checks: native 26-rule transaction/abort and IPv4 deny-only smoke passed. Real EE1→US2 core-crash failover/exhaustion passed; proxy-outage functional checks passed with timeout-inconclusive egress observations (overall no-leak verdict remains inconclusive). Cleanup/no-TUN/restored TCP passed. IPv6 unavailable; packet capture/DNS/reboot remain pending. See `.autopilot/host-validation.md`.
TUN aliases rotate per core start only after confirmed stop; readiness, shutdown and exact WFP LUID lookup must use manager.interface_name. Legacy and sing-tun-UUID aliases must be covered by recovery absence checks. find_process=true enables journal process metadata, verified live.
Native enumeration requires explicit layer GUIDs; zero layerKey fails with FWP_E_LAYER_NOT_FOUND. Preserve BOOTTIME/DISABLED enumeration.
Connection journal uses snapshots and can miss short-lived connections. See `.autopilot/PROGRESS.md` for unresolved acceptance work.
Protected IP refresh uses trust_env=False and a four-second UI deadline with stale-result checks; do not reintroduce unarmed-only refresh or inherited Windows proxy settings. Sniff precedes DNS routing; observed hostname enrichments update existing journal rows without destination override.
Live UiCheck verified protected IP and TLS example.com domain; Windows ProxyEnable remains on and must be treated as a potential browser-side conflict, never silently rewritten. Corrected local build: dist/fixed/KROTTUN.exe; see .autopilot/user-ip-domain-fix.md.
<!-- autopilot:end -->
