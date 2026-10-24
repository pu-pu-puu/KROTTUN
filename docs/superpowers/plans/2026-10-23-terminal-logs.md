# ASCII Terminal Logs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the user-approved ASCII terminal appearance for KROTTUN's connection log and deliver a rebuilt EXE.

## User scope correction — authoritative
User clarified: «нужно было заменить только сам лог а не всю вкладку», then supplied an orange rectangle. The rectangle includes the filter/pause/clear toolbar AND log viewport, below the existing title/source/help text. Terminal styling belongs ONLY inside this component. Everything outside it (blue background, logo/IP, navigation, protection controls, heading/help, warning) stays original. Remove body-wide styling, pixel hero and automatic window resizing; restore the native 520×760 layout. This correction supersedes the earlier expansion/body-mode requirements below. Keep selection, enrichment, filtering and privacy-safe text rendering.

**Architecture:** Scope styles to the connections view/body mode. Reuse existing journal polling; add frontend selected-row state, an accessible inspector and one UI-only bridge method to expand/restore the window. Keep all connection, IP, firewall and proxy logic untouched.

**Tech Stack:** Existing Python/pywebview, HTML/CSS/plain JavaScript, PyInstaller; no new dependencies or external font/network requests.

## Global Constraints
- User approved `design/log-prototypes-2026-10-23/04-ascii-reference.png` with «да пойдет».
- Pure black, lime/cyan, fine ASCII/dashed borders, compact native monospace, custom code-native pixel KROTTUN wordmark. No use of whole mockup as a background image.
- Scope: logs appearance plus row inspection only. Other tabs keep current design and behavior. Always retain navigation, native window controls, protection state/release and warning visibility.
- Only actual journal rows; no fake demo rows/counters/status values. Hostnames only when observed, raw values via textContent/attributes, no dynamic innerHTML.
- Source limitation persists: snapshots can miss short connections; no HTTPS body/path claims.
- No real network/firewall/TUN changes or live app launch for this visual task.
- Browser rejected local file rendering earlier; do not work around via localhost, Playwright, raw CDP or another browser. Static JS/HTML checks and non-rendering behavioral tests are allowed; do not claim visual browser QA.

## Task 1: Terminal log view and selection inspector

**Files:** Modify `gui/web/index.html` and only window-geometry handling in `gui/app_webview.py`; add focused tests under `tests/` for new behavior; update README only if needed to describe logs.

**Interfaces:** Existing connectionRows/connectionCursor/connectionPaused, renderConnections(), clearConnections(), switchTab(tab), get_connections() rows with connection_key, timestamp, process, destination, address, port, protocol, route, proxy_id. Produce frontend-only selected connection state/inspector and actual record count.

- [ ] Inspect current viewport/window sizing, header/nav, protection warning, journal upsert logic and approved image. Preserve all data and network boundaries.
- [ ] Add meaningful behavioral checks for selected-row lifecycle: selection remains on same connection_key after enrichment; missing/cleared selection resets details; filter and pause still behave; unsafe domain/process values remain text.
- [ ] Implement scoped terminal mode. Layout must fit existing app window with flex/min-height:0 and scrollable logs. Wordmark compact so useful rows remain visible. Use CSS/code-native pixel lettering; only local/system fonts. Include black surface, dashed +/box borders, readable lime/cyan values, bracket controls, no arbitrary intra-word wraps. At narrower widths prefer controlled horizontal scrolling over unreadable columns.
- [ ] Implement mouse/keyboard row selection, selected indicator, bottom details strip, actual visible/total count and honest source/protection state. Format app basename with full-path tooltip and domain as primary field; map route to known proxy country only when data exists, otherwise truthful fallback.
- [ ] Keep protection release and native window controls functional/accessibly visible. Entering/leaving logs toggles scoped class and restores original surrounding styling, without changing connection state.
- [ ] Existing native window is 520×760, resizable=False. Add a strict-boolean UI-only set_log_view(enabled) bridge method: entering logs expands toward ~1120×820 constrained to screen bounds, retains/restores exact prior size/position on exit, is idempotent and safe without a window reference. Avoid off-screen positioning and network operations; failed resize leaves functional scroll fallback. Test geometry with fake window/screen objects, never native live network code.
- [ ] Run static JavaScript syntax/HTML ID checks, focused behavior tests, full `python -m unittest discover -s tests` (baseline83), and one Impeccable detector pass. Report pinned-world exceptions for monospace/ASCII instead of removing them.
- [ ] Independent focused review, bounded fix batch, then root builds EXE into a fresh dist directory and verifies archive assets/modules/UAC. Never overwrite a running user's EXE.

## Handoff
User already chose the visual direction and the established Autopilot workflow uses one executor plus independent review. No additional process approval needed. Preview image and exact design prompt remain in `design/log-prototypes-2026-10-23/`.

## Result
Implementation completed; 87 tests and static JS/ID checks pass. Independent source review accepted DPI repair. Detector executed once; incumbent unrelated findings retained. Rebuilt and archive-verified dist/terminal/KROTTUN.exe. Visual rendering remains unverified under browser policy; details in .autopilot/terminal-log-delivery.md.
