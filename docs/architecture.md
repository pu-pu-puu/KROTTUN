# Runtime boundaries and data flow

KROTTUN is a Windows desktop application. `main.py` establishes the process entry point and administrator gate, then `gui/app_webview.py` owns the Python bridge exposed to the WebView UI in `gui/web/index.html`. The bridge coordinates persisted proxy records, selected proxy/settings, connection lifecycle, protection session, connection journal, and bounded diagnostics. UI calls return safe snapshots; credentials and `raw_line` stay on the Python side.

## Saved proxy controls and connection snapshots

`core/proxy_model.py` supplies proxy records; `core/storage.py` persists them using DPAPI and atomic writes. `edit_proxy` validates the explicit host, port, and SOCKS5/HTTP protocol, builds a replacement record, saves it, and restores the old list on storage failure. An omitted or empty password retains the existing secret; only the explicit clear flag removes it. Returned dictionaries omit both password and raw input. Edits update the saved list and apply on the next connection; they do not mutate an active runtime record.

Fallback configuration is an ordered list of proxy IDs in settings. A missing key retains legacy behavior by selecting all current proxies in their saved order; an explicit empty list means no fallback. IDs no longer present are discarded on read. The selected primary is always tried first, independently of fallback membership. At the start of each manual session, the bridge copies the primary and configured candidates once. `ProtectionSession` resolves hostname-bound endpoints before arming; after the initial attempt, the bridge freezes the matching verified numeric addresses in its private session queue before publishing `RUNNING`, then shares that immutable sequence with watchdog failover and exhaustion tracking. Failover advances through only the remaining snapshot; later edits or settings changes cannot silently alter the active sequence. Exhaustion remains deny-only until a manual retry.

## Protection lifecycle

The bridge serializes lifecycle operations separately from short state snapshots. `core/protection_session.py` coordinates the protected route policy and tunnel start/stop; `core/singbox_manager.py` owns the sing-box process and TUN runtime; `core/wfp_native.py` implements native Windows Filtering Platform operations. State/generation checks fence asynchronous work as lifecycle state changes. Protection persists through stop, error, and ordinary exit. Releasing it is explicit: stop the core and any diagnostic child, confirm process exit, then remove only KROTTUN policy. See the recovery and limitations section of `README.md` before network work; tests and this architecture note do not establish leak-prevention readiness.

## Diagnostics process boundary

`core/diagnostics.py` owns fixed diagnostic checks and runs transport requests in a separate spawned child, independent of manager health probes. The bridge accepts diagnostics only in a supported state: a healthy protected TUN, or an explicitly selected proxy while protection is unarmed and the core is idle. Protected mode sends no proxy endpoint or credentials; unarmed mode sends a copied selected record only. Direct-network fallback is forbidden. Requests disable inherited environment proxy settings, use fixed HTTPS/DoH targets, reject redirects, bound reads and time, and return only categorical results plus a validated public IP.

Every run is tied to IP/protection generations, process identity, TUN state, cancellation, and closing state; stale results are discarded. The worker request gate opens only after binding its process to the lifetime Job. Ownership is retained until exit is confirmed. Cancellation or release must not remove protected routing while a child may still be using it. The UI polls a single active run, renders its detached status snapshot, and cancels when dismissed; its total wait is capped at 12 seconds.

## Connection journal and UI

The connection journal combines lifecycle events with polling snapshots from the authorized loopback Clash API. It can miss short-lived connections. Observed HTTP Host or TLS SNI can enrich an existing row; sniffing precedes DNS routing, and enrichment does not replace the destination IP. HTTPS content is not decrypted or retained. The WebView renders bridge values as text and treats system proxy state as an advisory warning; it must not silently rewrite the Windows proxy setting.
