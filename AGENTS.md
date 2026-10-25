<!-- autopilot:start -->
# KROTTUN
Windows TUN proxy manager: Python, pywebview, sing-box, Wintun.

Release 2.6.5: 158 unittest checks pass (2026-10-25). Includes the three lifecycle audit fixes, aligned server dots, diagnostic placement C, Info passport A with backend APP_VERSION, and blocked-diagnostics banner A with valid-context reasons. Offline browser regressions for these screens and existing map/protection/icons/journal/proxy/ping flows pass. Build: `dist/v2.6.5/KROTTUN.exe`; embedded HTML/binaries/changed bytecode, multiprocessing hook and Administrator manifest verified. SHA-256: `ae585755e6b544496b14b486db14f30e25dac03e8fd8a632083b721ec0bf2e66`. Native/frozen runtime and remaining VM acceptance were not run. See `.autopilot/release-v2.6.5-verification.md`.

Verification: `python -m unittest discover -s tests` — 141 passed (2026-10-25). `node prototypes/ping-controls/verify.cjs` passes 480/520px geometry, HTTPS modes and ping UI regressions. Release 2.6.0 build: `dist/v2.6.0/KROTTUN.exe`; embedded sources/binaries, multiprocessing hook and Administrator manifest verified. SHA-256: `3fb2b953049ce9c9688d72153112bcb02b92299eb4d640d113db1616ab020338`. Native/frozen/live network checks were not run.
Manual ping: healthy protected RUNNING uses one bounded job-gated spawn child. Actual active manager proxy uses HTTPS204 through existing TUN (cp.cloudflare.com, then www.gstatic.com within the same deadline), never a self-endpoint probe; failed measurement is unavailable/unknown, not proxy dead. Other nodes use SOCKS5/HTTP protocol response through TUN; unarmed IDLE retains direct TCP connect. `latency_mode` persists tun_https/tun/tcp; modes must not be conflated. No policy exceptions or direct fallback. Release must confirm diagnostic and ping worker exit before removing policy. See `.autopilot/active-ping-fix.md` and `.autopilot/ping-layout-fix.md`.

Previous feature verification (cba2a4c): `python -m unittest discover -s tests` — 120 passed; independent clean clone installed the existing requirements in a fresh venv, `pip check` was clean, and all 120 tests passed with no skips. `node prototypes/proxy-controls/verify.cjs` passed. PyInstaller build passed; archive HTML/bin/module bytecode/main/multiprocessing hook/source were checked, with Administrator manifest. `dist/proxy-controls/KROTTUN.exe` SHA-256: `a99bafa2f95075d49e0baad4bac7db5c7d1236bc16e8858ff9b8e793cb208419`. Native GUI, frozen-helper runtime, and live network were not run for this feature. The user removed automatic window expansion; its API and obsolete geometry tests were removed. Earlier independent clean clone: 28 passed before host-harness additions.
`python -m core.kill_switch --help` exits 0; runtime imports verified. Existing dependencies only; fresh-environment installation was verified as above.
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
Tunnel probes use one killable spawn worker with a job-bound request gate; retain ownership until confirmed exit. Early main.freeze_support must precede app imports. DNS refresh is allowed only without policy; active cache requires matching hostname. Explicit release invalidates IP generation and connected_since. See `.autopilot/review-fixes-2026-10-23.md`; frozen-helper runtime remains unverified.
Protected IP refresh uses trust_env=False and a four-second UI deadline with stale-result checks; do not reintroduce unarmed-only refresh or inherited Windows proxy settings. Sniff precedes DNS routing; observed hostname enrichments update existing journal rows without destination override.
Live UiCheck verified protected IP and TLS example.com domain; Windows ProxyEnable remains on and must be treated as a potential browser-side conflict, never silently rewritten. Corrected local build: dist/fixed/KROTTUN.exe; see .autopilot/user-ip-domain-fix.md.
Proxy controls: edits validate explicit SOCKS5/HTTP and replace-and-save with rollback; omitted/empty password preserves the saved secret, explicit clear removes it, and safe bridge dictionaries never expose password/raw_line. Edits affect the next connection; a running session keeps its copied candidate snapshot and frozen numeric endpoints. Fallbacks have an explicit ordered ID list; missing setting means legacy all-proxy order, while `[]` means no fallback. Primary remains first even when absent from the fallback list. Diagnostics are a separate bounded spawn process, context-gated against stale state, with no direct fallback; protected release waits for confirmed child exit. Diagnostics UI deadline is at most 12 seconds. See [docs/architecture.md](docs/architecture.md) and final run record `.autopilot/2026-10-24-diagnostics-proxy-controls/`.
<!-- autopilot:end -->

## Git identity
- All new commits and GitHub publications must use `pu-pu-puu`.
- Git author/committer: `pu-pu-puu <282508417+pu-pu-puu@users.noreply.github.com>`.
- Before committing or publishing, verify the effective identity. Never use `ui-ux-promax` or another account.
