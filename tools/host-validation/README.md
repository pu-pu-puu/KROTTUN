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

Requires exactly one saved EE and one saved US as identified by the production
get_country_code(), no existing owned policy/recovery marker/core/GUI/sing-tun.
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
