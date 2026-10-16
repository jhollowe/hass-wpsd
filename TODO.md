# TODO

## WPSD changes needed

Features that cannot be done without modifying WPSD. None are blocking; see `research-output.md`.

- JSON status endpoint (modes enabled/paused/error, modem firmware, active mode, per-mode links). Today this data is only in server-rendered HTML (`radioinfo.php`, `repeaterinfo.php`), so we would have to scrape.
- Push mechanism (webhook/SSE) on last-heard changes, to avoid ~1 s polling.
- Document (or make explicit) which endpoints, e.g. `/api/`, are public vs. behind auth.

## Integration

- Pick up from `research-output.md` -> "What to check first when a live WPSD is available".
- Make credentials optional so users who only want the public (unauthenticated) data can skip the username/password.
- Config flow: test host and credentials against WPSD. Needs to know which endpoint is behind the login (the web server auth config is not in the reference repos; WPSD stores the admin password via `htpasswd` for user `pi-star`, i.e. likely HTTP basic auth).
- Work out which data is available without login.
- Decide how to detect short transmissions (fast polling vs. a push mechanism from WPSD).
- Implement client for WPSD-WebCode endpoints.
- Required entities: enabled-mode booleans, active mode sensor, firmware version.
- Nice-to-have: active connections/callsigns, linked network/talkgroup, transmitting boolean.

# Misc

- make WPSD version use bs4 instead of regex
  - make it actually find the correct version string/commit hash
- implement adding talkgroup/TS1/TS2/etc data as attributes on the mode sensors
- make sure mode sensors can support active, inactive, error, and paused as states
- test with more active repeater(s):
  - w0jrw.hopto.org
  - rpt.k0rq.com
  - f1zjh.dnsalias.org
  - dashboard-digital.w8woo.org (https)
  - http://gb7pg.ddns.net:8080/
  - https://n7uh.rvdv.org/
  - http://www.multimode.fr/ (only DMR, make sure missing other modes doesn't blow up)
  - http://www.proton.org.uk/ (cross modes)
