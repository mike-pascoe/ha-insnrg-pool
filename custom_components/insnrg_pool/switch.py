"""Switch platform for Insnrg Pool."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .app_api import InsnrgAppClient
from .const import (
    DOMAIN,
    RELAY_MODE_OFF,
    RELAY_MODE_ON,
    RELAY_MODE_TO_NAME,
    TYPE_SWITCH,
    relay_voice_device_id,
)
from .coordinator import InsnrgCoordinator
from .entity import InsnrgEntity, InsnrgRelayEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up every switch-typed Insnrg device."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.control
    entities: list[SwitchEntity] = [
        InsnrgSwitch(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device["type"] == TYPE_SWITCH
    ]
    entities.extend(_relay_switches(runtime))
    async_add_entities(entities)


def _relay_switches(runtime) -> list[SwitchEntity]:
    """Build switches for relay outlets the control API leaves out."""
    app_data = runtime.app.data or {}
    names = app_data.get("_custom_names") or {}
    return [
        InsnrgRelaySwitch(runtime.app, outlet, InsnrgAppClient.relay_name(names, outlet))
        for outlet in app_data.get("_relays") or {}
        if relay_voice_device_id(outlet) not in runtime.control.data
    ]


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


class InsnrgRelaySwitch(InsnrgRelayEntity, SwitchEntity):
    """A relay hub outlet reached through the app API.

    The app exposes one three-state mode for these rather than a separate
    power reading, so OFF is off and both ON and TIMER report on. Use the
    companion mode select when the distinction matters.
    """

    def __init__(self, coordinator, outlet: int, name: str) -> None:
        super().__init__(coordinator, outlet, name, f"relay_{outlet}")

    @property
    def is_on(self) -> bool | None:
        """Return true unless the outlet is switched off."""
        mode = self.mode
        return None if mode is None else mode != RELAY_MODE_OFF

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the underlying three-state mode."""
        mode = self.mode
        if mode is None:
            return None
        return {"mode": RELAY_MODE_TO_NAME.get(mode, mode)}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Force the outlet on, overriding any timer schedule."""
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_relay_mode(self._outlet, RELAY_MODE_ON)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the outlet off."""
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_relay_mode(self._outlet, RELAY_MODE_OFF)
        )
