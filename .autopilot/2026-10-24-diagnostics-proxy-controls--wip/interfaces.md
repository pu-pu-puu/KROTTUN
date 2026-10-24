# Границы, решённые в спецификации

## Правила проекта
- D:/Projects/KROTTUN; Python, pywebview, single HTML, sing-box. No new dependencies.
- Full check: python -m unittest discover -s tests. Single: python -m unittest discover -s tests -p test_proxy_edit.py (or relevant file).
- Do not launch app or EXE, no real firewall/network mutation, no stored proxy secrets read/printed. Read AGENTS.md and README recovery constraints.
- Other user work: modified .autopilot/PROGRESS.md and untracked host-capture artifacts; do not revert, stage or commit those. No worker commits; orchestrator commits scoped paths after reviews. Not alone in codebase.
- Runtime protection modules core/wfp_native.py, core/kill_switch.py, core/protection_session.py and existing manager probe lifecycle remain unchanged unless a proven blocker is reported.
- Fixed 520x760 window, background map/mesh, protection strip, terminal CSS preserved. Use native existing components and SVG icons. Product copy Russian.
- Git identity before every commit: pu-pu-puu <282508417+pu-pu-puu@users.noreply.github.com>. Never publish.

## Bridge and store
ProxyTunBridgeApi owns lifecycle, id-preserving edits, fallback settings/session snapshot and diagnosis lifecycle. RLock for short snapshots; _op_lock never held for diagnostic network operations. Password not in _proxy_to_dict, no new raw_line. ProxyItem.tag is name; expose tag in safe dictionary.
edit_proxy(proxy_id, host, port, protocol, username='', password=None, tag='', clear_password=False) -> {success, error?, proxies?, selected_proxy?}. password None/empty preserves old; explicit clear removes. Protocol explicit socks5/http, validation strict, no autodetect network in editing. Store replace-then-save with rollback; no mutation of old item. Return only safe dictionaries. clear caches and stale async geo only when identity matches.
get_fallbacks() -> {success, fallback_proxy_ids:[id], proxies:[safe], applies_next_connection:bool}; set_fallbacks(proxy_ids:list[str]) -> {success,error?,fallback_proxy_ids?}. settings key fallback_proxy_ids, missing key means legacy all current IDs; explicit [] remains empty. Atomic save setting then in-memory update; stale/missing IDs normalized when read. Session candidates snapshot copy once under _lock on each manual start, shared with watchdog and exhaustion tracking. Edits in RUNNING replace saved item only, never active runtime object/session snapshot; transitional/release edit is busy. Current primary always first regardless fallback membership; fallback list membership never changes primary selection.

## Diagnostics
core/diagnostics.py owns fixed check schema, bounded spawn worker and transport checks, isolated from manager health worker. Public helper/service signatures may be chosen by executor, then returned under INTERFACES.
Bridge start_diagnostics() -> {success,run_id?,busy?,error?}; get_diagnostics() -> {run_id,status,checks:[{id,label,status,detail}],...}. get returns safe detached snapshot immediately. One active run; duplicate start returns busy. Context includes _ip_gen, protection generation, process identity, TunState, cancel, closing. Each poll/worker completion verifies context before any result publication. Stop/release/shutdown invalidation as needed. Runtime checks healthy protected TUN or selected explicit proxy while unarmed/IDLE without running core. blocked/unknown/transitions skipped. Direct fallback forbidden. Unarmed DNS check is explicit DoH via selected proxy, not system DNS.
Check IDs: proxy,dns,https,ip,system_proxy. States running/pass/fail/warning/skipped. Static safe error categories, IP validated. Worker may receive a copied selected ProxyItem only in unarmed explicit-proxy mode via in-memory spawn args; never returns or logs its credentials. Protected mode receives no endpoints/credentials. Trust_env=False, fixed HTTPS targets, redirects disabled, bounded body reads, monotonic deadline. Worker job-bound before request gate opens; process ownership retained until confirmed exit. At most 12 sec UI/worker wall deadline. Test injection seams for transports/spawn/clock.

## UI
Editing and reserves use modal dialogs and existing server list. Diagnostic button may be in existing home server-actions or info area without altering protection panel geometry. UI polling single-flight, bounded timeout, stops when dialog closes; handles exceptions and stale run IDs. No unsanitized innerHTML; use DOM textContent for all data. Password fields cleared on close and successful save. Keep inputs after validation/storage errors.
