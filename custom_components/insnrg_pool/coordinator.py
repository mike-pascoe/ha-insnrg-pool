"""Data update coordinator for Insnrg Pool."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    InsnrgAuthError,
    InsnrgClient,
    InsnrgError,
    InsnrgVoiceControlDisabled,
)
from .app_api import InsnrgAppClient
from .const import DOMAIN, RELAY_SETTLE_SECONDS, WRITE_SETTLE_SECONDS

_LOGGER = logging.getLogger(__name__)


class InsnrgCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls the Insnrg cloud and holds the latest device snapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: InsnrgClient,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await self.client.async_get_devices()
        except InsnrgAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except InsnrgVoiceControlDisabled as err:
            raise UpdateFailed(str(err)) from err
        except InsnrgError as err:
            raise UpdateFailed(str(err)) from err

    async def async_settle_and_refresh(self) -> None:
        """Give the controller a moment to apply a write, then refresh state."""
        await asyncio.sleep(WRITE_SETTLE_SECONDS)
        await self.async_request_refresh()

    async def async_write_then_refresh(self, coro) -> None:
        """Await a write, then settle and refresh."""
        await coro
        await self.async_settle_and_refresh()


class InsnrgAppCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the Insnrg app API for maintenance telemetry.

    Kept separate from the control coordinator because this data changes
    slowly and is not worth polling at control cadence. Failures here are
    non-fatal: the integration stays usable without the diagnostics.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: InsnrgAppClient,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_app",
            update_interval=scan_interval,
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.async_get_dashboard()
            data["_relays"] = await self.client.async_get_relay_modes()
            return data
        except InsnrgError as err:
            raise UpdateFailed(str(err)) from err

    async def async_write_then_refresh(self, coro) -> None:
        """Await a relay write, let the controller apply it, then refresh.

        The register echoes the old value for a few seconds after a write, so
        this waits longer than the control API path does.
        """
        await coro
        await asyncio.sleep(RELAY_SETTLE_SECONDS)
        await self.async_request_refresh()

    async def async_config_entry_first_refresh_soft(self) -> None:
        """First refresh that logs rather than aborting setup on failure."""
        try:
            await self.async_config_entry_first_refresh()
        except Exception as err:  # noqa: BLE001 - diagnostics are optional
            _LOGGER.warning(
                "Insnrg maintenance telemetry unavailable, continuing without it: %s",
                err,
            )
