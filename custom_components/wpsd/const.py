"""Constants for the WPSD integration."""

from typing import Final

DOMAIN: Final = "wpsd"

DEFAULT_PORT: Final = 80
DEFAULT_USERNAME: Final = "pi-star"

# API endpoints
ENDPOINT_API: Final = "/api/"
ENDPOINT_HOMEPAGE: Final = "/"
ENDPOINT_RADIOINFO: Final = "/mmdvmhost/radioinfo.php"
ENDPOINT_REPEATERINFO: Final = "/mmdvmhost/repeaterinfo.php"

# Mode names as they appear in WPSD
MODE_D_STAR: Final = "D-Star"
MODE_DMR: Final = "DMR"
MODE_YSF: Final = "YSF"
MODE_P25: Final = "P25"
MODE_NXDN: Final = "NXDN"
MODE_POCSAG: Final = "POCSAG"
MODE_DMR_X_MODE: Final = "DMR X-Mode"
MODE_YSF_X_MODE: Final = "YSF X-Mode"

ALL_MODES: Final[list[str]] = [
    MODE_D_STAR,
    MODE_DMR,
    MODE_YSF,
    MODE_P25,
    MODE_NXDN,
    MODE_POCSAG,
]

# Sensor types
SENSOR_ACTIVE_MODE: Final = "active_mode"
SENSOR_FIRMWARE: Final = "firmware"
SENSOR_TX_FREQ: Final = "tx_freq"
SENSOR_RX_FREQ: Final = "rx_freq"
SENSOR_CPU_LOAD: Final = "cpu_load"
SENSOR_CPU_TEMP: Final = "cpu_temp"
SENSOR_DISK_USAGE_ROOT: Final = "disk_usage_root"
SENSOR_DISK_USED_ROOT: Final = "disk_used_root"
SENSOR_DISK_TOTAL_ROOT: Final = "disk_total_root"
SENSOR_DISK_USAGE_VARLOG: Final = "disk_usage_varlog"
SENSOR_DISK_USED_VARLOG: Final = "disk_used_varlog"
SENSOR_DISK_TOTAL_VARLOG: Final = "disk_total_varlog"

# Config entry data
CONF_VERIFY_SSL: Final = "verify_ssl"

# Options (polling intervals, in seconds)
CONF_MODE_SCAN_INTERVAL: Final = "mode_scan_interval"
CONF_SYSTEM_SCAN_INTERVAL: Final = "system_scan_interval"
DEFAULT_MODE_SCAN_INTERVAL: Final = 5
DEFAULT_SYSTEM_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 1
MAX_SCAN_INTERVAL: Final = 3600
