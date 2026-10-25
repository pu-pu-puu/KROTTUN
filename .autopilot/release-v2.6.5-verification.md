# Release 2.6.5 — verification

Date: 2026-10-25. Base: main/v2.6.0 c00c832ad37760864755310c0bb552a6f5732656.
User explicitly requested publication of 2.6.5 in the current chat.

- APP_VERSION and README badge updated to 2.6.5.
- Included: three audit lifecycle fixes, server-dot alignment, approved diagnostic
  placement C, Info passport A, and blocked-diagnostic banner A with context reasons.
- `python -m unittest discover -s tests`: 158 passed, 17.582s, OK.
- Browser PASS: diagnostic-placement dot and production verifiers, Info production,
  blocked-diagnostics production, proxy-controls, ping-controls, world-map production
  and protection-layout, icon runtime, connection-journal production.
- Browser transport requests aborted; app bridge mocked. EXE/GUI and real network
  settings were not operated. Native/frozen helpers/VM acceptance remain pending.
- PyInstaller exit 0: dist/v2.6.5/KROTTUN.exe, 44,142,955 bytes.
- SHA256: ae585755e6b544496b14b486db14f30e25dac03e8fd8a632083b721ec0bf2e66.
- Archive verifier PASS: exact embedded HTML/sing-box/Wintun and bytecode of bridge,
  diagnostics, version, ping, proxy model, IP worker/IP service, manager/win_job/main;
  multiprocessing runtime hook and requireAdministrator manifest present.
- Matching KROTTUN.exe.sha256 created. Release helper verifies upload digests and
  uploader before making its draft public, refusing an existing release overwrite.
- Git author/committer both pu-pu-puu with required noreply. GitHub connector and
  GCM API /user independently confirm pu-pu-puu; repository push permission true.
- Pre-existing PROGRESS.md and private host-validation/capture files excluded.
  Test-generated historical PNG modifications restored; design prototypes use
  documentation IPs and mocked transport only.

Release notes: .autopilot/release-v2.6.5.md. No network-safety certification claimed.
