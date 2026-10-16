# TODO

## WPSD changes needed

Features that cannot be done without modifying WPSD. None are blocking; see `research-output.md`.

- JSON status endpoint (modes enabled/paused/error, modem firmware, active mode, per-mode links). Today this data is only in server-rendered HTML (`radioinfo.php`, `repeaterinfo.php`), so we would have to scrape.
- Push mechanism (webhook/SSE) on last-heard changes, to avoid ~1 s polling.
- Document (or make explicit) which endpoints, e.g. `/api/`, are public vs. behind auth.

## Integration

- Decide how to detect short transmissions (fast polling vs. a push mechanism from WPSD).

# Misc

- implement adding talkgroup/TS1/TS2/etc data as attributes on the mode sensors
- test with more active repeater(s):
  - w0jrw.hopto.org
  - rpt.k0rq.com
  - f1zjh.dnsalias.org
  - https://dashboard-digital.w8woo.org/
  - http://gb7pg.ddns.net:8080/
  - https://n7uh.rvdv.org/
  - http://www.multimode.fr/ (only DMR, make sure missing other modes doesn't blow up)
  - http://www.proton.org.uk/ (cross modes, simplex)
