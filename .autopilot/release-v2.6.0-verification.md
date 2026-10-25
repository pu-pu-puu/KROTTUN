# Release 2.6.0 — verification

Дата: 2026-10-25.

- Source: current main includes the 10 unpublished commits after v2.5.0; all author/committer identities checked as pu-pu-puu. World-map session commits5f6c8c3 and b2a6a2a are ancestors of HEAD.
- Included world-map session: lower/brighter map,13 capital lights26 animations, preserved ambient dots; hidden pause/reduced motion; stable protection geometry; outline SVG icons; Blue Ice journal.
- Included current session: one-button diagnostics, id-preserving edit, explicit ordered reserve queue, isolated terminal, row geometry and bounded ping, corrected active-tunnel HTTPS metric.
- APP_VERSION=2.6.0; README badge and repository URL corrected.
- Full unittest:141 passed,11.854s,OK.
- Browser checks PASS: world-map/verify-production; world-map/verify-protection-layout; icons/verify-runtime; connections/verify-production; proxy-controls/verify; ping-controls/verify. Production HTML only, application bridge fake or removed; main/EXE never launched.
- PyInstaller KROTTUN.spec --noconfirm --distpath dist/v2.6.0 --workpath build/v2.6.0: exit0.
- Archive/source match: HTML,sing-box,Wintun; code of bridge,diagnostics,ping_service,proxy_model,version,main; multiprocessing hook; requireAdministrator manifest.
- KROTTUN.exe:44,135,423 bytes; SHA2563fb2b953049ce9c9688d72153112bcb02b92299eb4d640d113db1616ab020338. Sidecar KROTTUN.exe.sha256 created.
- GitHub connector and GCM independently identify pu-pu-puu; repository push permission verified. Release helper rechecks /user before mutation and asset uploader/digest before making draft public.
- Native GUI/live network/frozen helper tests not performed; VM/IPv6/DNS/reboot acceptance remains pending and is stated in release notes. Publication is explicitly requested by the user and does not claim network-safety certification.
- Test-generated historical screenshots restored; pre-existing PROGRESS/host-capture files remain local and outside the release commit.
