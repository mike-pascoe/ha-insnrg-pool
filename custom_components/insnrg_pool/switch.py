"""Switch platform for Insnrg Pool."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TYPE_SWITCH
from .coordinator import InsnrgCoordinator
from .entity import InsnrgEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up every switch-typed Insnrg device."""
    coordinator = hass.data[DOMAIN][entry.entry_id].control
    async_add_entities(
        InsnrgSwitch(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device["type"] == TYPE_SWITCH
    )


class InsnrgSwitch(InsnrgEntity, SwitchEntity):
    """A pool appliance, timer or heater that reports on/off."""

    def __init__(self, coordinator: InsnrgCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_name = coordinator.data[device_id]["name"]

    @property
    def is_on(self) -> bool | None:
        """Return true if the appliance is currently powered."""
        power = self.device.get("power")
        return None if power is None else power == "ON"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose timer mode, which the on/off state alone does not convey."""
        toggle = self.device.get("toggle")
        if toggle is None:
            return None
        return {"timer_mode": toggle == "ON"}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the appliance on."""
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_switch(self._device_id, "ON")
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the appliance off."""
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_switch(self._device_id, "OFF")
        )
