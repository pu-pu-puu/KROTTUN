# UI refinements — 2026-10-24

Approved and implemented in this session:
- Lower, brighter dotted world map with soft capital lights; ambient background dots preserved.
- Stable protection panel geometry through every state.
- Native window title KROTTUN — v2.5.0, sourced from core/version.py.
- Consistent outline SVG icons, including dynamic status and ping updates.
- Blue Ice connection journal, concise truthful source status and expandable explanation.

Validation: 99 unit tests passed. Isolated browser checks exercised map animation/reduced motion, stable protection geometry, dynamic icons and journal filtering/selection/pause/clear/source availability. New executables were built and embedded assets compared with sources. Native GUI/network behavior was not launched for these visual changes.

Latest local artifact: dist/blue-ice/KROTTUN.exe.
SHA256: 372dab8d82866d1676a8358f1f2af719f699b8b35535d1e6f11286950e3fa4b5.

Git identity corrected globally and locally to pu-pu-puu using the account's ID-based noreply email. Other GitHub entries removed from Git Credential Manager. Connected Codex GitHub profile was already pu-pu-puu. GitHub release v2.5.0 and its executable show pu-pu-puu as publisher/uploader; existing historical commits retain their original authorship.

Raw host packet captures and desktop-video frames are local-only. Separate host-validation scripts/reports predate this UI work and are not part of the UI commit.
