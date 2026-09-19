"""Constants for the Insnrg Pool integration."""

from __future__ import annotations

from typing import Any, Final

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

# Relay hub writes echo the previous register value briefly before settling.
RELAY_SETTLE_SECONDS: Final = 8

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

# --- Relay hub outlets driven through the app API -------------------------
# Outlets 3-6 on the relay hub are MODE_CHANNEL_EXP_1..4, at consecutive
# registers. Most appear in the control API as OUTLET_HUB_n, but an outlet the
# user has not surfaced in the app's appliance list is missing from it
# entirely, and the app API is then the only way to reach it.
RELAY_CMD_URL: Final = "https://95osjk2ux7.execute-api.us-east-2.amazonaws.com/prod/send"
RELAY_VALUES_URL: Final = "https://q5nhxjkqu4.execute-api.us-east-2.amazonaws.com/prod/items"
RELAY_DEVICE_TYPE: Final = "expansion"
RELAY_FIRST_OUTLET: Final = 3
RELAY_LAST_OUTLET: Final = 6
RELAY_FIRST_REG: Final = 65040
# The app names an outlet under this id offset in the system's customNames:
# outlets 3-6 are ids 505-508.
RELAY_NAME_ID_BASE: Final = 502

# Register encoding, all three confirmed against live hardware.
RELAY_MODE_OFF: Final = 0
RELAY_MODE_ON: Final = 1
RELAY_MODE_TIMER: Final = 2
RELAY_MODE_TO_NAME: Final = {
    RELAY_MODE_OFF: "OFF",
    RELAY_MODE_ON: "ON",
    RELAY_MODE_TIMER: "TIMER",
}
RELAY_NAME_TO_MODE: Final = {v: k for k, v in RELAY_MODE_TO_NAME.items()}


def relay_reg(outlet: int) -> int:
    """Return the MODE_CHANNEL_EXP register backing a relay hub outlet."""
    return RELAY_FIRST_REG + (outlet - RELAY_FIRST_OUTLET)


def relay_cmd(outlet: int) -> str:
    """Return the command name for a relay hub outlet."""
    return "MODE_CHANNEL_EXP_%d" % (outlet - RELAY_FIRST_OUTLET + 1)


def relay_voice_device_id(outlet: int) -> str:
    """Return the control API device id this outlet would use if exposed."""
    return "OUTLET_HUB_%d" % outlet


def as_float(value: Any, default: float | None = None) -> float | None:
    """Coerce an API value to float, tolerating blanks and junk.

    The Insnrg API intermittently reports "" for a reading whose probe is
    momentarily not answering. float("") raises, which is enough to stop an
    entity being added at all, so every reading goes through here.
    """
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
