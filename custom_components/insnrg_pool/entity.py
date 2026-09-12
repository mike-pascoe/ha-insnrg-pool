"""Shared entity base for Insnrg Pool."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import InsnrgCoordinator


class InsnrgEntity(CoordinatorEntity[InsnrgCoordinator]):
    """Base entity bound to one device id in the coordinator snapshot."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: InsnrgCoordinator,
        device_id: str,
        key_suffix: str = "",
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        system_id = coordinator.client.system_id
        suffix = f"_{key_suffix}" if key_suffix else ""
        self._attr_unique_id = f"{system_id}_{device_id}{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(system_id))},
            manufacturer=MANUFACTURER,
            name="Insnrg Pool",
            model="inTouch",
            serial_number=system_id,
            configuration_url="https://www.insnrgapp.com",
        )

    @property
    def device(self) -> dict[str, Any]:
        """Return this entity's slice of the coordinator snapshot."""
        return self.coordinator.data.get(self._device_id) or {}

    @property
    def available(self) -> bool:
        """Only available while the device is present in the snapshot."""
        return super().available and self._device_id in (self.coordinator.data or {})
