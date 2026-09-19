"""Climate platform for Insnrg Pool."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, THERMOSTAT_TARGET_KEYS, as_float
from .coordinator import InsnrgCoordinator
from .entity import InsnrgEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool and spa thermostats."""
    coordinator = hass.data[DOMAIN][entry.entry_id].control
    async_add_entities(
        InsnrgThermostat(coordinator, device_id)
        for device_id in THERMOSTAT_TARGET_KEYS
        if device_id in coordinator.data
    )


class InsnrgThermostat(InsnrgEntity, ClimateEntity):
    """A pool or spa heat setpoint.

    The API exposes a target temperature but no on/off for the thermostat
    itself -- heating is gated by the Gas Heater switch -- so the entity
    reports a single HEAT mode.
    """

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: InsnrgCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._target_key = THERMOSTAT_TARGET_KEYS[device_id]
        self._attr_name = coordinator.data[device_id]["name"]

    @property
    def _thermostat(self) -> dict[str, Any]:
        return self.device.get("thermostat") or {}

    @property
    def min_temp(self) -> float:
        """Return the lowest selectable temperature."""
        return as_float(self._thermostat.get("valueMin"), 10.0)

    @property
    def max_temp(self) -> float:
        """Return the highest selectable temperature."""
        return as_float(self._thermostat.get("valueMax"), 40.0)

    @property
    def current_temperature(self) -> float | None:
        """Return the measured water temperature."""
        return as_float((self.device.get("temperature") or {}).get("value"))

    @property
    def target_temperature(self) -> float | None:
        """Return the heat setpoint."""
        return as_float(self._thermostat.get(self._target_key))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new heat setpoint."""
        temperature = as_float(kwargs.get(ATTR_TEMPERATURE))
        if temperature is None:
            return
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_temperature(
                self._device_id, temperature
            )
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Only HEAT is supported; accepted as a no-op for automation safety."""
