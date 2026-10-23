Stage 1 uses production policy(), native _add(), and native readback in a WFP
transaction which is ALWAYS aborted. It never calls replace or commit.
It refuses existing owned filters or running KROTTUN/sing-box processes.

Run from PowerShell (a UAC prompt is expected):
  powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\KROTTUN\tools\host-validation\stage1.ps1

Reports: tools/host-validation/reports/stage1.json and stage1.txt.
No configuration, credentials, application identity, endpoints, or arbitrary
exception strings are written. Native error codes and phase are retained.
The code uses repository bin/sing-box.exe only for native application identity.
Documentation-only endpoint addresses and a synthetic interface LUID exercise
the production policy builder and ctypes ABI; they do NOT validate actual TUN
identity, real proxy reachability, packets, DNS, leaks, reboot, or recovery.
Stage 1 passed on the local host; stage 2 is a separate explicit live action.

Offline emergency recovery (explicit mutation; CLOSE GUI FIRST):
  powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\KROTTUN\tools\host-validation\RECOVER-MANUALLY.ps1

Recovery opens a visible elevated console and invokes existing
core.kill_switch --release. It is not automatic. Corrupt owned WFP metadata can
make the existing recovery command fail; retain errors for manual diagnosis.
No guarantee of restored internet follows from this helper.
Launchers use fixed project/Python paths; review them before changing location.
Do not edit project scripts while an elevated probe/recovery is running.

Stage 2 (LIVE, only after reviewing Stage 1):
  powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\KROTTUN\tools\host-validation\stage2.ps1

This commits the production deny/loopback/boot policy with no endpoint or TUN
exceptions, temporarily blocking direct connectivity for the whole PC. It first
requires IPv4 TCP connectivity to 1.1.1.1:443, an empty owned policy, stopped GUI
and core, and an aborted native add/delete rehearsal. An independent elevated
Python watchdog must open WFP, verify empty policy, and publish a per-run nonce
before parent arm. Its recovery target is 20 seconds, not a hard upper bound:
Windows scheduling, process termination and native APIs can delay recovery.
On expiry it verifies the direct test parent's PID, creation time, executable,
helper path and run nonce, then kills that exact parent and confirms exit BEFORE
deleting filters. This prevents a suspended parent resuming and committing after
watchdog cleanup. Unverified identity/exit or failed cleanup causes continued
recovery attempts, with no success report or watchdog exit. Normal parent signal
is sent only after the arm path has permanently ended. Parent also cleans up in
finally. Both delete ONLY the 14 deterministic
UUID5 smoke-filter keys, never metadata-discovered or foreign filters. Native
transaction cleanup readback must prove no owned filters remain.

The live test normally lasts only the TCP probe interval (under 5 seconds).
Only Windows 10013 on a new TCP connect counts as firewall denied. A timeout is
inconclusive. IPv6 is tested only if its baseline works; otherwise unavailable.
IPv4 connectivity must return after cleanup; watchdog success is also required.
Per-run events/results: reports/<nonce>/; latest result: reports/stage2.json.
No proxy credentials/config, DNS, TUN, packet capture or reboot are involved.
This is a connectivity smoke, not full leak prevention or release acceptance.
Independent watchdog mitigates parent failure, but cannot guarantee recovery if
Windows/BFE fails or the PC loses power. Keep manual recovery instructions offline.

Stage 3 inventory only (no WFP/TUN commit, requires same user's elevation for DPAPI):
  powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\KROTTUN\tools\host-validation\stage3.ps1 -InspectOnly

Stage 3 LIVE (review before first invocation):
  powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\KROTTUN\tools\host-validation\stage3.ps1

Uses the first saved EE and first saved US, preserving saved order within each
country, as identified by the production get_country_code(). Reports country
counts only; aborts if either country is missing. Requires no existing owned
policy/recovery marker/core/GUI/sing-tun.
Saved proxy list/settings are never written. The headless production bridge uses
in-memory clones, EE first and US reserve. Background IP/geo work is suppressed;
its real automatic failover watchdog and ConnectionSource remain enabled.
Reports contain phase, booleans/counts and sanitized error types/native codes;
no proxy host/IP/ID/credentials or raw connection/state payloads are dumped.
Production engine logs are redirected to the Windows null device. Production
recovery marker is created normally and removed only after verified cleanup.

The separate recovery watchdog starts BEFORE binding the parent to the core
kill-on-close Job Object. IsProcessInJob must prove the watchdog is outside that
job before any manager start. Recovery target is 100 seconds, not a hard OS/API
deadline. On expiry the watchdog terminates the verified exact parent, confirms
exit, waits until sing-box exit and sing-tun absence are verifiable, and only then removes all filters
in the OWNER sublayer across the six production layers (raw GUID enumeration,
boot/disabled included, no metadata decoding). Unconfirmed exit keeps retrying;
other processes are never killed. Residual TUN adapters are never deleted blindly;
they prevent policy release/marker removal/success until Windows removes them.
A newly started unrelated sing-box conservatively
delays release. Normal cleanup first permanently ends startup paths, stops the
core, verifies exit, then releases policy and signals the independent watchdog.

The test requires baseline connectivity/IP, EE running/reachable and changed
egress, an actual held TCP connection and live journal snapshot, primary core kill
with deny policy/new TCP blocked, production automatic US failover/changed egress,
then exhausted in-memory candidates with ERROR and blocked TCP. IP values remain
in memory. Missing 10013 is inconclusive/failure, not a leak-proof pass. Cleanup
requires no owned policy, no TUN and restored TCP. This still does not prove packet
capture/DNS/reboot/full leak prevention or release acceptance.

Selection/diagnosis options (no additional automatic attempts):
  stage3.ps1 -UsIndex 2 -AvailabilityOnly
  stage3.ps1 -UsIndex 2
  stage3.ps1 -UsIndex 2 -PrimaryCountry US

UsIndex is the one-based ordinal among saved US records, preserving their saved
order; EE remains the first saved EE. AvailabilityOnly checks ONLY this selected
pair using explicit proxy HTTPS to api.ipify.org, environment proxies disabled,
redirects disabled, request timeout 3 seconds, no geo lookup. It reports country,
saved ordinal, success and exception type only; the validated exit IP remains in
memory. No manager, TUN or WFP commit occurs. InspectOnly and AvailabilityOnly
are mutually exclusive. Availability result 'ok' means diagnostics completed;
each endpoint's success is reported separately.

Live failures now include bounded monotonic bridge/protection state samples,
active country (local ID mapping only), core running/reachable booleans, native
manager start/probe durations/boolean probe results and sanitized exception types
and native codes. In-progress start/probe calls remain visible at timeout. Journal
diagnostics aggregate only allowlisted failover/protection event states/counts.
Wrappers preserve the original production method results and exceptions. No raw
engine logs, saved proxy payloads, IDs, hosts or error messages are exported.
The 30-second wait is unchanged; timings can distinguish an unfinished manager
start from a completed failed health probe. Previous latest reports are copied
to stage3-before-diagnostics-<nonce>.json before replacement; per-run reports stay.

Adapter diagnostics now accompany bounded state samples and original _wait_ready
entry/exit: exact alias presence, number of sing-tun-prefixed aliases, expected
address present anywhere/exact alias, original return and child process poll facts.
No alias/address strings are exported. A small allowlisted classification inspects
startup exception text in memory only; unknown stays unknown. It is not a native
stderr capture. Core I/O and logging redirection remain unchanged. For isolation,
run the selected US proxy first using -UsIndex 2 -PrimaryCountry US; failover then
targets the first EE proxy. This is an explicit separate test, never automatic.

Debug startup diagnostics (harness only): generate_config copies the log settings,
sets debug level and removes log.output so the actual test core logs to stderr.
A manager-local subprocess proxy intercepts Popen only for its exact executable,
redirecting stderr to PIPE and draining on a daemon thread. It never changes the
returned child process or nonmatching subprocess calls. Raw chunks/pending lines
stay bounded in that thread (4096-byte chunks/pending line); no raw logs are saved
or included in reports. Reported per-start facts are fixed stage flags (default
interface found, TUN creation/start, route update, Clash listening, core started),
last allowlisted component, FATAL/ERROR flags, allowlisted reason and native codes.
Absence of a flag means only that no matching message was observed. Ordinary
production settings/code are unchanged. There is no automatic extra attempt.

Startup-fatal detail uses only fixed recognized phrases, API-operation labels and
at most 48 words from a fixed error vocabulary. Windows reasons include file/
already-exists, cannot-create-file, object-in-use, sharing violation, invalid
handle, device-not-ready, mutex and timeout. Operations distinguish Wintun adapter
create/open/session start, address/interface configuration and routes. Up to eight
startup error facts are retained per attempt, only before core-started is observed.
There is deliberately no fatal excerpt or raw text to redact: unknown words,
URLs, credentials, proxy fields, interface names, paths and addresses cannot enter
this schema. Recognized phrases are evidence; generic adapter-create alone still
does not identify the underlying Windows failure.

Complementary proxy-outage test (Core remains the default fault mode):
  powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\KROTTUN\tools\host-validation\stage3.ps1 -UsIndex 2 -FaultMode Proxy

Proxy mode withdraws the active endpoint permit under the production operation
lock, retaining only deny/loopback/boot plus the exact current TUN LUID. It does
not kill the core, call its probe, change probe results or alter watchdog timing.
The core must remain alive and policy armed. A controlled ipify check has a
three-second outer wait and two-second request timeout; only a completed network
exception other than timeout/HTTP status proves the injected failure. Observations
are fixed labels: network-failure, timeout-inconclusive, http-response,
successful-response and invalid-inconclusive. Only network failure and timeout
continue to functional failover checks; actual HTTP/public success or invalid
payload aborts. A timeout NEVER passes the negative test. If functional failover,
exhaustion and cleanup all succeed but any negative check timed out, functional_ok
is true, classification is inconclusive, ok stays false and the script exits
nonzero. No IP is output. The real production health probe
then drives reserve failover. Both automatic-failover/exhaustion waits allow 45
seconds (normal 30-second health interval + 2.5-second probe + core startup margin).
The independent recovery deadline remains 100 seconds. Core mode retains its
original behavior/waits. Exhaustion clears candidates only in memory, withdraws
the US endpoint permit with core alive, then requires ERROR, armed policy and TCP
10013. Final cleanup is unchanged. Packet capture/DNS/IPv6/reboot remain separate.

Production route.find_process is enabled so connection snapshots can report process
metadata even when protected routing has no process rules. Actual availability
still depends on the native engine and observed connection; the harness reports
the live boolean rather than manufacturing process fields.
