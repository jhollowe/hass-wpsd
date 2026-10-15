# WPSD research output

Findings from reading the reference repos (no live WPSD instance was available). Everything here is from source
code unless marked **UNVERIFIED**. File paths are relative to `reference_repos/WPSD-WebCode/` unless noted.

## TL;DR

- WPSD has **one JSON endpoint** (`/api/?limit=N`, last-heard only). Everything else the dashboard shows is
  **server-rendered HTML fragments** that the browser re-fetches on a timer. There is no websocket/SSE/push.
- Mode enabled/paused state, firmware version, and links all come from **config files and logs on the Pi**, rendered into
  HTML. Without WPSD changes we have to either scrape that HTML or find some other exposed source.
- "Transmitting now" and "active mode" are derived from the **last-heard list** (`/api/`) and are scrape-free.
- Auth is **UNVERIFIED**: the PHP does no auth; it appears to be nginx HTTP basic auth. Needs a live check.

## How the dashboard polls (the "no push" problem)

| Fragment | Interval | Source |
|---|---|---|
| `/mmdvmhost/radioinfo.php` (radio status, TX/RX/idle, firmware) | 1 s | `index.php:359-361` |
| `/mmdvmhost/repeaterinfo.php` (modes enabled, networks, links) | 5 s | `index.php:380-382` |
| `/mmdvmhost/last_heard_table.php`, `local_tx_table.php` | 1.5 s (>=4 cores) / 2.5 s | `index.php:694-700` |
| `/mmdvmhost/live_caller_backend.php` (live caller page) | `live/index.php:25` setInterval | `live/index.php` |
| `/includes/hw_info.php` | 30 s | `index.php:353` |

The dashboard itself polls at 1 s for TX state, so a 1-2 s poll is what WPSD's own UI achieves. Very short
transmissions can still be missed by a poller, but the **last-heard list persists finished transmissions**, so we
can detect them after the fact (see "Detecting short transmissions").

## Endpoints worth using

### `GET /api/?limit=N[&names=false][&country=false]` (JSON) — `api/index.php`
Returns the N most recent last-heard rows. Use `names=false&country=false` to avoid per-row `grep` lookups on the Pi
(each name lookup shells out to `grep` against `stripped.csv`, so keep polls cheap).

Fields: `time_utc`, `mode`, `callsign`, `name`*, `country`*, `callsign_suffix`, `target`, `src`, `duration`, `loss`.
(*omitted when disabled.) These map to the internal row `[timestamp, mode, callsign, id, target, source, duration,
loss, ber, rssi, alias]` (`mmdvmhost/functions.php:1203`); note the API drops `ber`, `rssi` and `alias`.

Key semantics (from `radioinfo.php:75-80`):
- **Transmission in progress** = row with a callsign, `duration` empty/null, and `src != "RF"`
  (i.e. the dashboard's "TX: <mode>" cell). RX in progress is the same with `src == "RF"`.
  **UNVERIFIED** how `duration` serialises in JSON for an in-progress row (null vs empty string) — check live.
- `mode` for DMR includes the slot (`"DMR Slot 2"`); the dashboard strips it with `preg_split('#\s+#', ...)[0]`.
- `/api/` is not described as auth-protected in the PHP, but see Auth below.

### HTML fragments (scrape only if nothing else works)
- `/mmdvmhost/radioinfo.php`: the status cell reads `TX: <mode>`, `RX: <mode>`, `Standby: <mode>`, `IDLE` or
  `OFFLINE`. This is the dashboard's definition of "active mode". Also shows the modem firmware cell (last div).
- `/mmdvmhost/repeaterinfo.php`: "Modes Enabled" and "Network Status" pills with classes `active` / `paused` /
  `error` / `inactive`, plus per-mode link text (D-Star reflector, DMR master/TGs, YSF/P25/NXDN reflector).
- Both depend on `$_SESSION` populated by `checkSessionValidity()` (they include it themselves), so they should be
  fetchable standalone. **UNVERIFIED** until tried against a real server.

### `admin/system_api.php` (JSON) — needs auth
Documented in the file header: `curl -u pi-star:raspberry 'http://localhost/admin/system_api.php?action=...&format=json'`.
Actions: `shutdown, reboot, get_ip, update_wpsd, stop_wpsd_services, restart_wpsd_services, update_hostfiles,
reload_wifi`, plus `bm_manager` / `sysx_manager` commands. Control-only; nothing for status. **Do not** expose
shutdown/reboot as HA entities without deliberate thought. This file is also the strongest evidence that `/admin/*`
uses HTTP basic auth.

## Mapping to the requirements

### Required
1. **Boolean per mode enabled** (D-Star, DMR, YSF, P25, NXDN, POCSAG, plus X-modes DMR X-Mode / YSF X-Mode)
   - Source of truth: MMDVMHost config `[Mode] Enable=1` (`getEnabled`, `functions.php:186`), with "paused" =
     `/etc/<Mode>_paused` exists and `Enable=0` (`isPaused`, `functions.php:464`).
   - Not exposed as JSON. Options: scrape `repeaterinfo.php` pills (`status-pill active|paused|error|inactive`), or
     TODO a WPSD change (see below).
   - Pill semantic: `active` = enabled and MMDVMHost running; `error` = enabled but MMDVMHost not running;
     `paused`; `inactive` = disabled. So a pill can give enabled + healthy in one value.
   - Mode labels in pills: `D-Star`, `DMR`, `YSF`, `P25`, `NXDN`, `POCSAG`, `DMR X-Mode`, `YSF X-Mode`. P25/NXDN/POCSAG
     are hidden for DVMega Cast hardware (`isDVmegaCast()`).
2. **Which mode is currently active**
   - `getActualMode()` (`functions.php:1238`): the mode of the newest last-heard row, held for the configured
     `ModeHang` seconds after the transmission ends (+ the transmission duration), then `idle`. Hang time comes from
     MMDVMHost config (`General ModeHang`, else per-mode `ModeHang`/`RFModeHang`).
   - Reproduce from `/api/?limit=1`: we know mode, `time_utc`, `duration`. **We do not know the hang time** without the
     config, so either scrape `radioinfo.php` (gives `Standby: X` vs `IDLE` directly) or make hang time an option.
3. **Firmware version**
   - Dashboard shows `$_SESSION['DvModemFWVersion']`, which is `ModemFW` from `/etc/WPSD-release`
     (`functions.php:87-88`). That file is generated by `WPSD-Scripts/.wpsd-sys-cache`, which parses the MMDVMHost log
     line `description: MMDVM ...` into e.g. `MMDVM_HS_Hat-v.20230322` (`.wpsd-sys-cache:215-250`). Falls back to
     `ModemType` if the log has no match, so the value can be a hardware name rather than a version.
   - The "WPSD Dashboard Version" is a git short hash (`config/version.php`) and is a different thing from modem firmware.
   - Not JSON-exposed. Scrape the last cell of `radioinfo.php` (the "Modem Type"/firmware column).

### Niceties
- **Active connections with callsigns:** last-heard rows (`callsign`, `target`, `src`, `mode`) cover who has been
  heard. The "currently connected" notion differs per mode; the dashboard only shows last-heard activity and the
  *link target*, not a list of connected users. (A live-caller view exists at `live_caller_backend.php`.)
- **Which network/talkgroup is linked:** per-mode, derived from different sources:
  - D-Star: `/var/log/pi-star/Links.log` (`getDSTARLinks`, `functions.php:1310`)
  - YSF / NXDN / P25: gateway log text parsing (`getActualLink`, `functions.php:1393+`)
  - DMR: config (`DMR Network Address`, or `DMRGateway` networks via `/usr/local/etc/DMR_Hosts.txt`), static/dynamic
    TGs from BrandMeister/TGIF/SystemX APIs; `RemoteCommand <port> status|hosts` is executed server-side for
    connection state (`repeaterinfo.php:62-90`).
  - Practically all HTML-only. Scrape `repeaterinfo.php` or request a WPSD JSON endpoint.
- **Transmitting boolean:** derivable from `/api/?limit=N` as above (in-progress row with `src != "RF"`).
  RF-originating traffic (`src == "RF"`) is reception from a local radio; the dashboard labels that `RX`. Decide in HA
  whether "transmitting" means WPSD→radio (network traffic) only, matching the dashboard's `TX:` label.

## Detecting short transmissions

- Poll `/api/?limit=1..5&names=false&country=false` at ~1-2 s (matching the dashboard).
- Keep the last seen `(time_utc, callsign, mode, target)` tuple. A new tuple => emit an HA **event** entity /
  fire a bus event even if we never observed the in-progress state. This catches transmissions shorter than the
  poll interval, since finished calls remain in the list with a `duration`.
- Use `duration` on the finished row to set a "last transmission" sensor and to reconstruct that a TX happened.
- For true live state, the in-progress row (no duration) is what we can catch only when polling lands inside it.
- A cleaner fix would be a WPSD-side push; recorded in `TODO.md` / below as optional.

## Authentication — UNVERIFIED, needs live host

- PHP code has no login logic. `session_id('wpsdsession')` is a fixed shared ID, not a per-user session.
- `WPSD-WebCode/admin/configure.php:975` sets the password with `htpasswd -b /var/www/.htpasswd pi-star <pw>`, and
  `system_api.php`'s header shows `curl -u pi-star:...`. Together this suggests nginx HTTP basic auth, user `pi-star`.
- The nginx config is **not in any reference repo** (`WPSD-Scripts` only restarts nginx / handles certs), so we do not
  know which locations require auth. It is likely `/admin/*` is protected and the main dashboard + `/api/` are public,
  which would match the user's note that "some info is available without logging in". Needs confirmation.
- HTTPS: `WPSD-Scripts/wpsd-gensslcert` exists, so some installs may serve HTTPS with a self-signed cert. The config flow
  likely needs an "SSL / verify certificate" option.

## What to check first when a live WPSD is available

1. Auth boundary (run unauthenticated, then with `-u pi-star:<pw>`):
   ```
   for p in / /api/?limit=1 /mmdvmhost/radioinfo.php /mmdvmhost/repeaterinfo.php /admin/ /admin/system_api.php?action=get_ip; do
     printf '%s -> ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "http://<host>$p"
   done
   curl -sI http://<host>/admin/ | grep -i www-authenticate
   ```
2. Capture real responses into `tests/fixtures/` (sanitise callsigns/IDs if sharing):
   - `/api/?limit=5&names=false&country=false` while idle and **during** a transmission (note how `duration` serialises)
   - `/mmdvmhost/radioinfo.php` for each of: idle, TX, RX, standby, MMDVMHost stopped (OFFLINE)
   - `/mmdvmhost/repeaterinfo.php` with each enabled mode, a paused mode, and a stopped service
3. Confirm the fragments render standalone (no dashboard session cookie), and measure their response time on a Pi Zero
   class host before choosing a poll interval (`repeaterinfo.php` runs several `exec()` calls per request).
4. Check HTTP vs HTTPS and the default port; confirm the redirect behaviour.
5. Confirm `/etc/WPSD-release` `ModemFW` really appears in the radioinfo firmware cell and what it looks like on the
   user's hardware.
6. Check whether a faster/cleaner source exists on the Pi that does not need WPSD changes (e.g. MMDVMHost remote
   control port via `RemoteCommand`, which is local-only and not reachable over HTTP).

## Proposed design (to confirm after live checks)

- **Client** (`custom_components/wpsd/api.py`): `aiohttp` via HA's shared session; optional `BasicAuth`; methods
  `get_last_heard()`, `get_radio_status()` (scrape), `get_repeater_status()` (scrape). Use `beautifulsoup4`-free
  parsing if possible (regex on the `status-pill` classes) to avoid adding a requirement; revisit once real HTML is in hand.
- **Coordinators:** one fast (1-2 s) for `/api/`, one slow (5-10 s) for the scraped fragments, so cheap data is not
  throttled by expensive pages. Mark the fast one with `update_interval` configurable in options.
- **Entities:**
  - `binary_sensor` per mode: enabled (+ attributes: paused, error)
  - `sensor` active mode (enum: idle, D-Star, DMR, YSF, P25, NXDN, POCSAG)
  - `sensor` modem firmware (diagnostic)
  - `binary_sensor` transmitting
  - `sensor` per-mode link target; `sensor` last heard (callsign, target, source as attributes)
  - `event` entity for completed transmissions
- **Options flow:** poll interval, optional credentials (see TODO.md), SSL verify.
- **Tests:** build from captured fixtures; no network.

## Candidate WPSD changes (nothing blocking; log these in TODO.md "WPSD changes needed")

1. A JSON status endpoint (e.g. `/api/status`) returning modes enabled/paused/error, firmware, active mode, links.
   This would replace both HTML scrapes with stable, cheap, parseable data.
2. A push mechanism (webhook or SSE) on last-heard changes, so HA need not poll every second.
3. Make `/api/` explicitly public or explicitly authenticated and document it.

## Open questions

- Which locations require auth (see "What to check first", item 1)?
- HTTP only or HTTPS with a self-signed cert by default?
- Does `/api/` `duration` serialise as `null`, `""`, or omit the key for an in-progress row?
- How does the user want "transmitting" defined: network-originated only (dashboard `TX:`), or any activity?
- Multi-hotspot support: one config entry per host (current assumption) is fine.
- DVMega Cast / `dvmpicast` hardware changes which modes and columns appear; support it or ignore it?
