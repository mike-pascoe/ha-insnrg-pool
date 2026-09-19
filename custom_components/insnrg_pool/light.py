"""Light platform for Insnrg Pool."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TYPE_LIGHT
from .coordinator import InsnrgCoordinator
from .entity import InsnrgEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pool lights."""
    coordinator = hass.data[DOMAIN][entry.entry_id].control
    async_add_entities(
        InsnrgLight(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device["type"] == TYPE_LIGHT
    )


class InsnrgLight(InsnrgEntity, LightEntity):
    """A pool light, with its colour programs exposed as effects."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, coordinator: InsnrgCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_name = coordinator.data[device_id]["name"]
        self._cached_effects: list[str] = list(
            coordinator.data[device_id].get("options") or []
        )

    @property
    def effect_list(self) -> list[str]:
        """Return the colour programs, keeping the last non-empty list."""
        live = list(self.device.get("options") or [])
        if live:
            self._cached_effects = live
        return self._cached_effects

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        power = self.device.get("power")
        return None if power is None else power == "ON"

    @property
    def effect(self) -> str | None:
        """Return the active colour program."""
        mode = self.device.get("mode")
        return mode if mode in self.effect_list else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose whether the light is following the timer schedule."""
        toggle = self.device.get("toggle")
        if toggle is None:
            return None
        return {"timer_mode": toggle == "ON"}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally selecting a colour program."""
        client = self.coordinator.client
        effect = kwargs.get(ATTR_EFFECT)
        was_on = self.is_on
        if effect is not None:
            await client.async_set_light_mode(self._device_id, effect)
        if not was_on:
            await client.async_set_switch(self._device_id, "ON")
        await self.coordinator.async_settle_and_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.async_write_then_refresh(
            self.coordinator.client.async_set_switch(self._device_id, "OFF")
        )
