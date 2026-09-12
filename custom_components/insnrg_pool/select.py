"""Select platform for Insnrg Pool."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TYPE_CHLORINATOR, TYPE_LIGHT, TYPE_PUMP_SPEED, TYPE_SWITCH
from .coordinator import InsnrgCoordinator
from .entity import InsnrgEntity

MODE_OPTIONS = ["ON", "OFF", "TIMER"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pump speed, chlorinator level and timer-mode selects."""
    coordinator = hass.data[DOMAIN][entry.entry_id].control
    entities: list[SelectEntity] = []

    for device_id, device in coordinator.data.items():
        if device["type"] in (TYPE_PUMP_SPEED, TYPE_CHLORINATOR) and device["options"]:
            entities.append(InsnrgModeSelect(coordinator, device_id))
        elif (
            device["type"] in (TYPE_SWITCH, TYPE_LIGHT)
            and device.get("toggle") is not None
        ):
            # Devices that support TIMER need a three-state control; the plain
            # switch can only express on/off.
            entities.append(InsnrgTimerModeSelect(coordinator, device_id))

    async_add_entities(entities)


class InsnrgModeSelect(InsnrgEntity, SelectEntity):
    """Pump speed or chlorinator output level."""

    def __init__(self, coordinator: InsnrgCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_name = coordinator.data[device_id]["name"]
        self._attr_options = list(coordinator.data[device_id]["options"])

    @property
    def current_option(self) -> str | None:
        """Return the selected level."""
        mode = self.device.get("mode")
        return mode if mode in self._attr_options else None

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
