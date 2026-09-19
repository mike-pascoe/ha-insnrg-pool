"""Select platform for Insnrg Pool."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .app_api import InsnrgAppClient
from .const import (
    DOMAIN,
    RELAY_MODE_TO_NAME,
    RELAY_NAME_TO_MODE,
    TYPE_CHLORINATOR,
    TYPE_LIGHT,
    TYPE_PUMP_SPEED,
    TYPE_SWITCH,
    relay_voice_device_id,
)
from .coordinator import InsnrgCoordinator
from .entity import InsnrgEntity, InsnrgRelayEntity

MODE_OPTIONS = ["ON", "OFF", "TIMER"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pump speed, chlorinator level and timer-mode selects."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.control
    entities: list[SelectEntity] = []

    for device_id, device in coordinator.data.items():
        if device["type"] in (TYPE_PUMP_SPEED, TYPE_CHLORINATOR):
            entities.append(InsnrgModeSelect(coordinator, device_id))
        elif (
            device["type"] in (TYPE_SWITCH, TYPE_LIGHT)
            and device.get("toggle") is not None
        ):
            # Devices that support TIMER need a three-state control; the plain
            # switch can only express on/off.
            entities.append(InsnrgTimerModeSelect(coordinator, device_id))

    app_data = runtime.app.data or {}
    names = app_data.get("_custom_names") or {}
    entities.extend(
        InsnrgRelayModeSelect(
            runtime.app, outlet, InsnrgAppClient.relay_name(names, outlet)
        )
        for outlet in app_data.get("_relays") or {}
        if relay_voice_device_id(outlet) not in coordinator.data
    )

    async_add_entities(entities)


class InsnrgModeSelect(InsnrgEntity, SelectEntity):
    """Pump speed or chlorinator output level."""

    def __init__(self, coordinator: InsnrgCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_name = coordinator.data[device_id]["name"]
        self._cached_options: list[str] = list(
            coordinator.data[device_id].get("options") or []
        )

    @property
    def options(self) -> list[str]:
        """Return the selectable levels.

        The API occasionally omits `options` on an otherwise healthy device,
        so the last non-empty list is kept rather than collapsing to nothing.
        """
        live = list(self.device.get("options") or [])
        if live:
            self._cached_options = live
        return self._cached_options

    @property
    def current_option(self) -> str | None:
        """Return the selected level."""
        mode = self.device.get("mode")
        return mode if mode in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Set a new level."""
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_pump_value(self._device_id, option)
        )


class InsnrgTimerModeSelect(InsnrgEntity, SelectEntity):
    """Three-state control for appliances that can follow the timer schedule."""

    _attr_options = MODE_OPTIONS

    def __init__(self, coordinator: InsnrgCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, key_suffix="mode")
        self._attr_name = f"{coordinator.data[device_id]['name']} mode"

    @property
    def current_option(self) -> str | None:
        """Return TIMER when following the schedule, else the power state."""
        device = self.device
        if device.get("toggle") == "ON":
            return "TIMER"
        power = device.get("power")
        if power is None:
            return None
        return "ON" if power == "ON" else "OFF"

    async def async_select_option(self, option: str) -> None:
        """Switch between manual on, manual off and timer control."""
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_switch(self._device_id, option)
        )


class InsnrgRelayModeSelect(InsnrgRelayEntity, SelectEntity):
    """Three-state mode for a relay hub outlet reached through the app API."""

    _attr_options = MODE_OPTIONS

    def __init__(self, coordinator, outlet: int, name: str) -> None:
        super().__init__(coordinator, outlet, f"{name} mode", f"relay_{outlet}_mode")

    @property
    def current_option(self) -> str | None:
        """Return ON, OFF or TIMER."""
        mode = self.mode
        return None if mode is None else RELAY_MODE_TO_NAME.get(mode)

    async def async_select_option(self, option: str) -> None:
        """Switch between manual on, manual off and timer control."""
        value = RELAY_NAME_TO_MODE.get(option)
        if value is None:
            return
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_relay_mode(self._outlet, value)
        )
