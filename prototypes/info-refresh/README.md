# Info / UAC proposal — awaiting user selection

Open index.html: A passport cards, B compact single sheet, C status plus details.
Only prototype files are changed; production Info, Python and EXE are untouched.
Version is read from core/version.py by build.cjs. Future production integration
must expose the same authoritative APP_VERSION through the bridge, rather than
hardcoding the prototype's version string into the application.

Source findings:
- Telegram row calls toggleBypassTelegram; backend set_bypass_telegram rejects
  direct exceptions, while the JS ignores unsuccessful responses.
- Compatibility leak warning and direct ag_dns text are static legacy strings.
  Protected generate_config instead enables strict_route, removes direct rules
  and DNS-direct, sets proxy-out as final, and rejects IPv6/UDP.
- DoH Cloudflare/Google has a TCP DNS fallback through proxy-out; do not describe
  every DNS attempt as HTTPS-only.
- State and admin privileges do not prove leak prevention or route readiness.
  Existing VM acceptance remains pending. An unknown state stays unknown.

Prototypes present Telegram as read-only, separate mode rules from runtime state,
show version 2.6.0 and preserve a precise verification caveat without claiming a
measured leak. Header/navigation/protection strip retain the existing identity.
The gallery offers running/unarmed/unknown demo states with no OS mutation.

Build: node prototypes/info-refresh/build.cjs
Verify/render: node prototypes/info-refresh/verify.cjs — PASS 2026-10-25.
480/520 layouts fit the initial viewport; no horizontal overflow, external
requests or page errors. Details support keyboard activation. Version, wording
and demo-state updates checked. Two visual inspection rounds completed.
Mechanical detector observations concern inherited map/dots/glow/easing only;
these incumbent styling choices remain outside this scoped proposal.

## User approved A — implemented

Production Info now uses passport A. `get_state.app_version` comes from
APP_VERSION; the initial view has no guessed version, privilege or readiness.
Refresh updates version/admin explicitly, and telemetry updates connection state.
Errors or missing state show unavailable/unknown rather than stale success.
Admin rights do not imply tunnel readiness. Running without confirmed reachability
shows a separate message. Old Telegram toggle JS and stale routing/leak claims
were removed; the backend's prohibition on direct exceptions remains unchanged.

Verification: authoritative version unittest, `verify-production.cjs` (480/520,
running/starting/stopping/error/idle/unreachable, missing state, bridge error,
changed version and absent admin rights), ping regression and diagnostic C
placement regression PASS. Production screenshot: production-a-520.png.
EXE not rebuilt in this step.
