# Audit corrections — 2026-10-25

Scope: the three P2 findings from audit c00c832. No live network, GUI,
WFP, route, DNS commands, dependency installation, or publication.

1. Reproduce ignored Job assignment with a mocked application startup. Require
   successful self-binding before constructing the bridge; verify the core's
   exact Job membership before handing it its configuration.
2. Reproduce stalled DNS cleanup with a fake subprocess. Bound the flush and
   termination waits; retain ownership and block lifecycle completion when exit
   cannot be confirmed. DNS flush failure with confirmed exit is best effort.
3. Reproduce stale/stalled IP queries and release while a worker remains alive.
   Use a single spawn child, request gate after Job binding, a three-second
   parent deadline plus bounded cleanup, bounded streamed response, context
   validation, retained ownership, and a release/shutdown barrier.
4. Run focused regressions, the full unittest suite, and review the diff.

Existing unrelated working-tree edits must be preserved. Native crash behavior,
frozen helper execution and VM packet capture remain separate acceptance work.

## Result

All three corrections implemented. `python -m unittest discover -s tests`:
154 tests, 14.036s, OK. Focused coverage includes Job startup/core rejection,
DNS timeout and retained ownership, streamed IP body limit, stale contexts,
real spawn fixtures with no transport (success, stall, cancellation, repeat),
closed request gates, orphan retention, release and shutdown refusal.
`git diff --check` passed (line-ending normalization warning only).
Independent read-only review found the missing shutdown barrier during the first
pass; a RED/GREEN regression and the barrier were added. Second pass found no
remaining substantive issues.

Test-harness corrections: the initial startup regression did not mock WebView
entry points and hung; its test process was stopped, and UI calls are now mocked.
The initial full-suite run still mocked the old in-process IP function, allowing
IP queries through the new child; these fixtures now mock the process service.
No sing-box, WFP, route, Windows proxy or system DNS mutation was performed.
EXE build/native GUI crash/frozen helper/VM acceptance were not performed.
Existing user changes in PROGRESS.md and host-capture materials were preserved.

## EXE build requested by user

2026-10-25: PyInstaller 6.22.3 / Python 3.14.6, exit 0.
Output: `dist/audit-fixes/KROTTUN.exe`, APP_VERSION 2.6.0, 44,139,992 bytes.
SHA256: `3052ac59a164c369863f75b28a26e62c9380ebba93ac99a7d1e9fe0f05f57573`.
Read-only archive verification passed: embedded HTML/sing-box/Wintun equal to
source; bytecode of bridge, diagnostics, version, ping service, proxy model,
IP worker, IP service, manager, win_job and main matches current source.
Multiprocessing runtime hook and requireAdministrator manifest are present.
The verifier was extended to cover the corrected modules and native manifest.
The executable was not launched; frozen/native runtime remains unverified.
