"""Number platform for Insnrg Pool -- pH and ORP setpoints."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHEMISTRY_BOUNDS, CHEMISTRY_DEVICES, DOMAIN
from .coordinator import InsnrgCoordinator
from .entity import InsnrgEntity

SETPOINT_NAMES = {"PH": "pH setpoint", "ORP": "ORP setpoint"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the chemistry setpoints."""
    coordinator = hass.data[DOMAIN][entry.entry_id].control
    async_add_entities(
        InsnrgSetpoint(coordinator, device_id)
        for device_id in CHEMISTRY_DEVICES
        if device_id in coordinator.data
    )


class InsnrgSetpoint(InsnrgEntity, NumberEntity):
    """A pH or ORP target the chlorinator doses towards.

    Bounds come from a fixed table rather than the API: the payload's
    `valueMax` for pH tracks the current reading rather than a real limit.
    """

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: InsnrgCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, key_suffix="setpoint")
        self._attr_name = SETPOINT_NAMES.get(device_id, f"{device_id} setpoint")
        low, high, step = CHEMISTRY_BOUNDS[device_id]
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = "mV" if device_id == "ORP" else None

    @property
    def native_value(self) -> float | None:
        """Return the current setpoint."""
        value = (self.device.get("thermostat") or {}).get("setPoint")
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new setpoint."""
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_chemistry(self._device_id, value)
        )
