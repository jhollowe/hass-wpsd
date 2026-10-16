I would like to make an integration for Home Assistant which gets information from WPSD, a digital radio control software.
The repos for Home Assistant and WPSD are available in in `reference_repos/`.

The webUI for WPSD polls for changes instead of being event driven. Since communications can be short, we either need a very fast polling frequency or find a way to notified of updates by WPSD.
Most of the interfacing to WPSD is in the WPSD-WebCode repo but other WPSD repos are available here for reference.

I would like to do as much as possible without changing any WPSD code. If there turns out to be features which requires WPSD changes, make note of it in TODO.md and we will address it later.

Bare minimal requirements:

- boolean sensor showing which of the modes (e.g. YSF or P.25) are enabled
- sensor showing which (if any) mode is currently active/in use
- firmware version
- TX frequency
- RX frequency
- CPU usage
- CPU temperature
- disk usage
- network traffic

Niceties:

- active connections, including callsigns
- what internet connections are active and which talkgroup is linked
- boolean showing when we are transmitting

look at https://www.hacs.xyz/docs/contribute/ and https://www.hacs.xyz/docs/publish/ for how to create a custom integration repo which can be used with Home Assistant Community Store (HACS).
