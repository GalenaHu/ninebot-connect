"""Ninebot Connect constants and verified endpoint policy."""

from homeassistant.const import Platform

DOMAIN = "ninebot_connect"
NAME = "九号车联"
VERSION = "0.3.0"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]
DEFAULT_POLL_INTERVAL = 120
MIN_POLL_INTERVAL = 30
MAX_POLL_INTERVAL = 3600
CONF_POLL_INTERVAL = "poll_interval"
PASSPORT = "https://api-passport-bj.ninebot.com"
BUSINESS = "https://api-jhcx-v6-bj.ninebot.com"
VEHICLES = "https://ebike.ninebot.com"
LOGIN_PATH = "/v6/user/login"
REFRESH_PATH = "/v3/user/refresh"
BUSINESS_LOGIN_PATH = "/user/user/login"
LIST_PATH = "/vehicle/binding/my-vehicle"
DYNAMIC_PATH = "/v6/vehicle/vehicle-dynamic-data"
STATUS_PATH = "/vehicle/vehicle/vehicle-status"
BATTERY_PATH = "/v6/vehicle/battery-info"
CONF_ADAPTIVE = "adaptive_polling"
CONF_BATTERY_DETAILS = "battery_details"
CONF_SHOW_LOCATION = "show_location"
ALLOWED_ROUTES = frozenset(
    {
        (PASSPORT, LOGIN_PATH),
        (PASSPORT, REFRESH_PATH),
        (BUSINESS, BUSINESS_LOGIN_PATH),
        (VEHICLES, LIST_PATH),
        (VEHICLES, DYNAMIC_PATH),
        (VEHICLES, STATUS_PATH),
        (VEHICLES, BATTERY_PATH),
    }
)
CLIENT_VERSION = "610063322"
# Public SDK client material shared by the official app, not an account secret.
CLIENT_KEY = "e177176a-3b3e-1513-e26e-d1123034cb66"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
