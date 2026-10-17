# TODO

## WPSD changes needed

Features that cannot be done without modifying WPSD. None are blocking; see `research-output.md`.

- JSON status endpoint (modes enabled/paused/error, modem firmware, active mode, per-mode links). Today this data is only in server-rendered HTML (`radioinfo.php`, `repeaterinfo.php`), so we would have to scrape.
- Push mechanism (webhook/SSE) on last-heard changes, to avoid ~1 s polling.
- Document (or make explicit) which endpoints, e.g. `/api/`, are public vs. behind auth.

## Integration

- Decide how to detect short transmissions (fast polling vs. a push mechanism from WPSD).

## Integration Quality Scale follow-ups

Bronze through Gold were checked by hand against core's rules, and `strict-typing` is `done` (mypy passes in CI). hassfest skips `quality_scale.yaml` for custom integrations, so none of this is machine-verified.

- `async-dependency` is `todo` in `quality_scale.yaml`. BeautifulSoup parses full HTML pages on the event loop on every poll. Measure it and decide whether to parse in an executor (`hass.async_add_executor_job`).
- `"quality_scale": "gold"` in `manifest.json` is a hand-checked claim. Decide whether to keep it, or drop it until the tier can be verified.
- `discovery` and `discovery-update-info` are `exempt` only because no mDNS/SSDP service record was found in the WPSD sources. Check a real hotspot (e.g. `avahi-browse`) in case the image advertises one.
- `repair-issues` is `exempt`. Consider a repair issue when a hotspot has been unreachable for a long time.
- `icons.json` has no entries for `cpu_temp`; it relies on the device class default icon.

## Docs and tests

- README "Supported devices" lists no tested WPSD versions. Add the versions and hardware that have been tried.
- `translations/en.json` was generated from `strings.json` with an ad-hoc script. Regenerate it with core's translations tool and diff.

# Misc

- implement adding talkgroup/TS1/TS2/etc data as attributes on the mode sensors
- allow a mode polling speed in seconds
- support HTTPS WPSD hosts
- check simplex gets correctly parsed
- check that APRS shows up
- test with more active repeater(s):
  - w0jrw.hopto.org
  - rpt.k0rq.com
  - f1zjh.dnsalias.org
  - https://dashboard-digital.w8woo.org/
  - http://gb7pg.ddns.net:8080/
  - https://n7uh.rvdv.org/
  - http://www.multimode.fr/ (only DMR, make sure missing other modes doesn't blow up)
  - http://www.proton.org.uk/ (cross modes, simplex)
