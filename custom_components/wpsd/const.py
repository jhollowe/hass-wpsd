"""Constants for the WPSD integration."""

import logging
from typing import Final

DOMAIN: Final = "wpsd"

LOGGER = logging.getLogger(__package__)

ENDPOINT_API: Final = "/api/"
ENDPOINT_HOMEPAGE: Final = "/"
ENDPOINT_RADIOINFO: Final = "/mmdvmhost/radioinfo.php"
ENDPOINT_REPEATERINFO: Final = "/mmdvmhost/repeaterinfo.php"

MODE_D_STAR: Final = "D-Star"
MODE_DMR: Final = "DMR"
MODE_YSF: Final = "YSF"
MODE_P25: Final = "P25"
MODE_NXDN: Final = "NXDN"
MODE_POCSAG: Final = "POCSAG"

ALL_MODES: Final[list[str]] = [
    MODE_D_STAR,
    MODE_DMR,
    MODE_YSF,
    MODE_P25,
    MODE_NXDN,
    MODE_POCSAG,
]

# Mode/network status values rendered by WPSD (status-pill CSS classes)
MODE_STATE_ACTIVE: Final = "active"
MODE_STATE_INACTIVE: Final = "inactive"
MODE_STATE_ERROR: Final = "error"
MODE_STATE_PAUSED: Final = "paused"
MODE_STATES: Final[list[str]] = [
    MODE_STATE_ACTIVE,
    MODE_STATE_INACTIVE,
    MODE_STATE_ERROR,
    MODE_STATE_PAUSED,
]

CONF_MODE_SCAN_INTERVAL: Final = "mode_scan_interval"
CONF_SYSTEM_SCAN_INTERVAL: Final = "system_scan_interval"
DEFAULT_MODE_SCAN_INTERVAL: Final = 5
DEFAULT_SYSTEM_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 1
MAX_SCAN_INTERVAL: Final = 3600
