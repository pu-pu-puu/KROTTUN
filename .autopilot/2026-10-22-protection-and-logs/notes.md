# Repository exploration — protection and connection journal

## Existing APIs and lifecycle

- Active desktop UI: `gui/app_webview.py`, `gui/web/index.html`. `gui/app.py` is an older UI; keep compatible but implement the exposed pywebview bridge first.
- `ProxyTunBridgeApi`: `_lock` is an RLock for short state reads; `_op_lock` serializes start/stop. Existing states: idle, starting, running, stopping, error. `_closing`, `_ip_gen`, `_error_seq`, `_last_error`, `_probe_fail_count` already implement shutdown, stale-IP-response protection and error delivery.
- `get_state()` returns running/state/reachability/errors, connected_since, admin, system_ip, speed strings, active_proxy, selected_proxy, proxies, settings. `get_telemetry()` polls status/IP/speed every second. Browser has home/servers/info tabs and in-flight polling protection. New protection/journal API should return bounded data, with secrets retained in Python.
- `toggle_tun()` starts daemon `_do_toggle(target)`; `_do_toggle` holds `_op_lock`, selects proxy/settings, invokes `SingBoxManager.start()` or stop, updates state, then refreshes public IP. `select_proxy()` and `set_bypass_telegram()` restart through the same operation path. `shutdown()` sets closing, cancels geo workers, takes `_op_lock`, and stops sing-box.
- Watchdog checks process every 1.5 seconds and connectivity roughly every 30 seconds (3 consecutive misses mark unreachable, ~90 seconds). A process death currently changes state to error and stops sing-box; no firewall protection or proxy failover exists. Health result identity checks should use a session generation plus process/proxy identity, not only RUNNING.
- `SingBoxManager.start(proxy, bypass_telegram=False)` begins with stop(), resolves/builds config, verifies binaries, spawns `sing-box run -c stdin`, waits for sing-tun/198.18.0.1, then `_probe_tunnel` for up to 6 seconds. It returns True even when `proxy_reachable` is False. Failover must test actual reachability. Password-bearing config stays on stdin; do not introduce on-disk configs or command arguments with credentials.
- `stop()` gracefully signals its own process, then terminate/kill fallback, closes stderr, waits for adapter disappearance, clears active_proxy/reachable, flushes DNS. It must not implicitly disarm a persistent kill switch during failover, crash cleanup, errors or shutdown.
- Startup binds app and descendants to a Windows Job Object (`core/win_job.py`). This closes the engine when app dies but does not prevent Windows default routes from leaking after adapter removal.

## Configuration and leaks

- Existing config logs warn to `sing-box.log`; stderr has separate file; start truncates logs. These files are operational diagnostics, not a connection journal.
- TUN uses auto_route=True, strict_route=False, IPv4 address only, excludes loopback and RFC1918. IPv6 rejection is a sing-box route rule, therefore cannot protect traffic bypassing TUN or after process death.
- Explicit direct routes exist for proxy IP/host, xray.exe, AG_2.21.1.exe, ag_dns.exe, optional Telegram.exe, localhost and private IPs. Local DNS suffixes use direct resolver. These conflict with the requested full protection. In protected mode remove public direct process exceptions and Telegram bypass; LAN policy must be explicit. Strict routing alone is not an independent persistent kill switch.
- Proxy hostname bootstrap uses `_resolve_v4()` with unbounded getaddrinfo, returns /32 even if supplied IPv6 literal; fix endpoint family handling and bounded resolution. Resolution while protected must not silently open direct DNS. Resolve before arming for a user initiated connect, cache numeric endpoints, fail closed when cache unavailable; reconnect/failover should use cached IP endpoints without changing proxy credentials. A protected session cannot refresh hostnames with arbitrary host DNS.
- `_refresh_ip_async`, geo worker, protocol detection and pings perform network work. Independent guard must constrain these as ordinary app traffic. Disable unnecessary geo/background probes while blocked; do not give the Python GUI a broad direct allow. `_probe_tunnel` uses normal requests through routing rather than explicit proxy transport: only meaningful with independently verified guard and TUN routing. Bound health/retry traffic and avoid duplicate failover workers.

## Persistent firewall recommendation

Do not create a blanket Windows Defender Firewall outbound Block plus narrower Allow rules: explicit Block takes precedence. DefaultOutboundAction=Block plus endpoint Allow is also insufficient alone: existing broad outbound Allow rules bypass the desired policy, and modifying/disabling unrelated rules creates restore/conflict hazards.

Preferred implementation is a narrowly owned Windows Filtering Platform provider/sublayer with atomic transactions, non-dynamic persistent filters, explicit IPv4 AND IPv6 policy, scoped loopback/TUN permissions and a fail-closed physical-egress block. Permit only the verified protected sing-box executable to the selected cached proxy IP and port, including required UDP only for SOCKS. Engine must send traffic via proxy only in protected config. Use weighted exceptions and catch-all within the same owned sublayer according to WFP arbitration; never assume Windows Firewall rule precedence applies to WFP. Avoid hard permit flags that override unrelated security products. Confirm exact layer/interface conditions for ALE_AUTH_CONNECT_V4/V6 and reauthorization/established flows on Windows in isolated acceptance tests. Do not claim that an untested interface condition protects forwarded traffic.

A WFP implementation must be reviewed as native ABI code (ctypes structures, union layout, UTF16 buffers, GUIDs, byte order, handle lifetime and return codes); never pass a bare numeric constant where a correctly typed FWP_VALUE/condition is needed. Runtime persistent filters survive app death; reboot early-start needs separate boot-time coverage because BOOTTIME and PERSISTENT cannot coexist on one filter. This is a separate implementation/VM acceptance requirement, not a guarantee obtained by setting one flag. Fail closed on BFE/firewall/transaction/ownership failures and report the exact enforcement error; protection state is not simply a saved checkbox.

Persist owned filter identities and recovery metadata in the existing trusted data location before activation; reconcile actual native state on startup. Snapshot/restore only owned policy. Explicit user unlock removes owned filters; normal disconnect, exhaustion, app shutdown, failed launch and crash retain block. Keep a documented local elevated recovery action available independent of GUI. New proxy endpoint policy must be installed transactionally before stopping old engine, and old endpoint permissions retired after success or failure without a transient open policy. Avoid changing live network state during development.

## Failover seam

One coordinator invoked under `_op_lock` should own both user connect and watchdog failover. States should distinguish blocked, switching, connecting and verified protected connection. Snapshot eligible proxy IDs, exclude current/failed entries, try bounded candidates once, back off, permit cancellation/closing, and leave persistent block on exhaustion. Never turn stale health success into RUNNING for a replacement process. Preserve the selected-vs-active distinction and make failover’s resulting active server visible. Bound retries and health checks; do not repeatedly probe every proxy in a tight loop.

## Journal seam

Use authenticated loopback-only sing-box Clash controller (`experimental.clash_api.external_controller`, random per-session secret) from Python to gather supported connection metadata. Verify bundled 1.14.x binary exposes required API and `/connections` behavior before relying on schema. Do not expose controller token or unrestricted arbitrary URL bridge to JavaScript. UI calls a dedicated bounded journal API. Snapshot polling can miss short-lived connections: label coverage honestly; if every connection attempt is required, add a bounded engine event stream with verified route/outcome data. Do not infer blocked connections from their absence in `/connections`.

Records: timestamp/session/proxy ID, source process when actually known, destination host/IP/port, protocol, observed route/chain, state, byte counts. Mark unavailable metadata explicitly. Never log credentials, authorization headers, bodies, URL paths/query strings or TLS plaintext. No HTTPS decryption. Use bounded in-memory retention, optional explicit export, redact secrets/control characters and render via textContent. Persist only if required and under private ACL with rotation limits. Capture protection/failover lifecycle in the same bounded journal as separate event kinds.

## Storage and tests

- `ProxyItem`: id/host/port/protocol/username/password/tag/latency/location/last_status. `core/storage.py` DPAPI-encrypts proxies; `_atomic_write_file` uses fsync/replace and reparse checks. `load_settings()` defaults bypass_telegram=False, v=2 and merges unknown fields. `save_setting(key,value)` updates atomically under module lock. Settings are per-SID in ProgramData/ProxyTUN/users/<SID>, private ACL; binaries/logs under trusted ProgramData/ProxyTUN. Machine-wide firewall ownership cannot rely solely on per-user settings.
- Existing tests: `python -m unittest discover -s tests`; single `tests/test_regression.py`, 15 regression tests (baseline confirmed by parent). Covers binary hash/version/config check, multi-tier DNS, explicit protocol selection, bounded DNS, captive-portal probe rejection, real local mock SOCKS/HTTP sockets, sanitization, DPAPI storage isolation and shutdown safety. Tests patch secure root/user dirs and use loopback mock servers; do not call live firewall or launch TUN.
- Add fake firewall backend/transaction executor tests for arm-before-start, persistence across stop/shutdown/failure, recovery ownership, v4/v6 conditions and endpoint restrictions, failover ordering/exhaustion/cancellation/stale-generation, settings validation, bounded/redacted journal and cursor behavior. Native integration acceptance requires an isolated Windows VM for process kill/app kill/reboot, adapter changes, IPv4/v6/DNS, pre-existing broad Allow rules and restoration; do not replace that with mocks or local host firewall mutation.

## Primary references checked 2026-10-22

- Windows Firewall rule precedence: https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/rules
- WFP flags and structures: https://learn.microsoft.com/en-us/windows/win32/api/fwpmtypes/ns-fwpmtypes-fwpm_filter0
- Boot-time to persistent transition: https://learn.microsoft.com/en-us/windows/win32/fwp/basic-operation
- sing-box authenticated controller configuration: https://sing-box.sagernet.org/configuration/experimental/clash-api/

Only this notes artifact was written; no project code or live network/firewall state changed.

