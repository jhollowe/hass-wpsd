# WPSD

Home Assistant integration for [WPSD](https://wpsd.radio), digital radio hotspot
control software.

> [!NOTE]
> Work in progress: the integration is in early development and the entities
> and options described below may change.

> [!NOTE]
> This repo is made with the assistance of an LLM.

## Installation

The integration can be installed using HACS. The integration is not available
in the default repositories, so you will need to add the URL of this repository
(`https://github.com/jhollowe/hass-wpsd`) as a custom repository in HACS
(category: Integration).

Alternatively you can use the button below.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jhollowe&repository=hass-wpsd&category=Integration)

After installing, restart Home Assistant and add the integration under
Settings → Devices & services.

## Description

This integration is used to get the status of a WPSD hotspot. WPSD has no
JSON status API, so the integration polls the dashboard's HTTP pages and
parses the HTML. No login is used, so only the data the dashboard shows
publicly is available.

The device is named after the hotspot's callsign, taken from the dashboard
page title. If no callsign is found it is named `WPSD`. The device's software
version is the dashboard's git commit hash.

## Entities Provided

Where applicable the sub-items in the list detail the additional attributes
available. All entities may not be available to you depending on what your
WPSD dashboard shows.

### Sensors

| Location | Name | Enabled by default | Primary value | Additional Information | Comments |
|---|---|:---:|---|---|---|
| Device | Active Mode | ✔️ | Current radio status text shown by the dashboard | | |
| Device | Modem Firmware Version | ✔️ | Firmware version of the modem | | |
| Device | TX Frequency | ✔️ | Transmit frequency in MHz | | |
| Device | RX Frequency | ✔️ | Receive frequency in MHz | | |
| Device | CPU Load | ✔️ | CPU load in % | | |
| Device | CPU Temperature | ✔️ | CPU temperature in °C | | |
| Device | / Disk Usage | ✔️ | Usage of the `/` filesystem in % | | |
| Device | / Disk Used | | Space used on `/` in GB | | |
| Device | / Disk Total | | Size of `/` in GB | | |
| Device | /var/log Disk Usage | ✔️ | Usage of the `/var/log` filesystem in % | | |
| Device | /var/log Disk Used | | Space used on `/var/log` in GB | | |
| Device | /var/log Disk Total | | Size of `/var/log` in GB | | |
| Mode | D-Star | ✔️ | Status of the mode; `active`, `inactive`, `error` or `paused` | Network status | One sensor each for D-Star, DMR, YSF, P25, NXDN and POCSAG. Network status has the same values as the primary value and is only present if the dashboard reports one. |

# Setup

## `Add Integration` button

If adding the integration by clicking the `Add Integration` button the
following information will be requested.

* `Host`: The hostname or IP address of the WPSD hotspot's dashboard.
* `Port`: The port of the dashboard web server, default `80`.

The integration checks that the dashboard can be reached before it is added.
Only plain HTTP is supported at the moment.

## Configurable Options

It is possible to configure the following options for the integration. They
are found by clicking `CONFIGURE` on the integration. Changing an option
reloads the integration.

### Polling

* `Mode status polling interval`: the frequency of updates for the mode
  sensors, default `5s`
* `System stats polling interval`: the frequency of updates for the other
  sensors, default `30s`

Both accept values from `1` to `3600` seconds. Options are set per hotspot, so
a less powerful device can be polled less often than the others.

## Troubleshooting

### Debug Logging

Debug logging can be enabled in Home Assistant using the [`logger`
integration](https://www.home-assistant.io/integrations/logger/).

```yaml
logger:
  default: warning
  logs:
    custom_components.wpsd: debug
```
