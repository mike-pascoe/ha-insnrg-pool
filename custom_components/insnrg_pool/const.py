"""Constants for the Insnrg Pool integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "insnrg_pool"
MANUFACTURER: Final = "Insnrg"

API_BASE: Final = "https://4rsb9rvte4.execute-api.us-east-2.amazonaws.com/prod/api"
LOGIN_URL: Final = f"{API_BASE}/login"
CMD_URL: Final = f"{API_BASE}/cmd"

CONF_SCAN_INTERVAL_MINUTES: Final = "scan_interval_minutes"
DEFAULT_SCAN_INTERVAL_MINUTES: Final = 5

# Maintenance counters move in hours, not minutes.
APP_SCAN_INTERVAL_MINUTES: Final = 30

# Seconds to wait after a write before re-polling. The cloud needs a moment to
# round-trip the command to the pool controller before `getall` reflects it.
WRITE_SETTLE_SECONDS: Final = 3

# Alexa-style namespaces the `getall` payload reports state under.
NS_POWER: Final = "Alexa.PowerController"
NS_TOGGLE: Final = "Alexa.ToggleController"
NS_THERMOSTAT: Final = "Alexa.ThermostatController"
NS_TEMPERATURE: Final = "Alexa.TemperatureSensor"
NS_MODE: Final = "Alexa.ModeController"

# Device "type" values returned by the API.
TYPE_SWITCH: Final = "SWITCH"
TYPE_LIGHT: Final = "LIGHT"
TYPE_THERMOSTAT: Final = "THERMOSTAT"
TYPE_PUMP_SPEED: Final = "PUMP_SPEED"
TYPE_CHLORINATOR: Final = "CHLORINATOR"

# Thermostat-typed devices that are really water-chemistry probes, not heaters.
CHEMISTRY_DEVICES: Final = {"PH", "ORP"}

# Thermostat-typed devices that are real heat setpoints, mapped to the key the
# API uses to report their target (as opposed to the current reading).
THERMOSTAT_TARGET_KEYS: Final = {
    "POOL_CONTROL": "ggPoolSetTemperature",
    "SPA_CONTROL": "ggSpaSetTemperature",
}

# Fallback bounds used when the API does not report sane min/max for a probe.
CHEMISTRY_BOUNDS: Final = {
    "PH": (7.0, 8.0, 0.1),
    "ORP": (550.0, 750.0, 10.0),
}
