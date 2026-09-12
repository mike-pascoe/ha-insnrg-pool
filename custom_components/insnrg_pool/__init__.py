"""The Insnrg Pool integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InsnrgAuthError, InsnrgClient, InsnrgError
from .app_api import InsnrgAppClient
from .const import (
    APP_SCAN_INTERVAL_MINUTES,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)
from .coordinator import InsnrgAppCoordinator, InsnrgCoordinator
from .models import InsnrgRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Insnrg Pool from a config entry."""
    client = InsnrgClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        await client.async_login()
    except InsnrgAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except InsnrgError as err:
        raise ConfigEntryNotReady(str(err)) from err

    minutes = entry.options.get(
        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
    )
    coordinator = InsnrgCoordinator(hass, entry, client, timedelta(minutes=minutes))
    await coordinator.async_config_entry_first_refresh()

    # Maintenance telemetry lives on a different Insnrg API. It is optional:
    # if it fails we still set up, just without the diagnostic sensors.
    app_client = InsnrgAppClient(
        hass,
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    app_coordinator = InsnrgAppCoordinator(
        hass, entry, app_client, timedelta(minutes=APP_SCAN_INTERVAL_MINUTES)
    )
    await app_coordinator.async_config_entry_first_refresh_soft()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = InsnrgRuntimeData(
        control=coordinator, app=app_coordinator
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when the poll interval option changes."""
    await hass.config_entries.async_reload(entry.entry_id)
