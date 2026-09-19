"""Sensor platform for Insnrg Pool."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, as_float
from .coordinator import InsnrgAppCoordinator
from .entity import InsnrgAppEntity, InsnrgEntity

PH_ORP_SENSORS = {
    "PH": ("pH", None, None),
    "ORP": ("ORP", "mV", SensorDeviceClass.VOLTAGE),
}


@dataclass(frozen=True, kw_only=True)
class InsnrgAppSensorDescription(SensorEntityDescription):
    """Describes a sensor sourced from the app API dashboard."""

    value_fn: Callable[[dict[str, Any]], Any]


def _counter(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda data: (data.get(key) or {}).get("value")


APP_SENSORS: tuple[InsnrgAppSensorDescription, ...] = (
    InsnrgAppSensorDescription(
        key="totalhours",
        translation_key="cell_life",
        name="Cell life",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_counter("totalhours"),
    ),
    InsnrgAppSensorDescription(
        key="phHours",
        name="pH probe life",
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_counter("phHours"),
    ),
    InsnrgAppSensorDescription(
        key="orpHours",
        name="ORP probe life",
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_counter("orpHours"),
    ),
    InsnrgAppSensorDescription(
        key="acidHours",
        name="Acid squeeze tube life",
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_counter("acidHours"),
    ),
    InsnrgAppSensorDescription(
        key="gasHeaterHours",
        name="Gas heater hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_counter("gasHeaterHours"),
    ),
    InsnrgAppSensorDescription(
        key="cell_voltage",
        name="Cell voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_counter("cell_voltage"),
    ),
    InsnrgAppSensorDescription(
        key="cell_current",
        name="Cell current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_counter("cell_current"),
    ),
    InsnrgAppSensorDescription(
        key="wifiSignalStrength",
        name="WiFi signal",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_counter("wifiSignalStrength"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up chemistry readings and maintenance telemetry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for device_id in PH_ORP_SENSORS:
        if device_id in runtime.control.data:
            entities.append(InsnrgChemistrySensor(runtime.control, device_id))

    if "POOL_CONTROL" in runtime.control.data:
        entities.append(InsnrgWaterTempSensor(runtime.control, "POOL_CONTROL"))

    app_data = runtime.app.data or {}
    entities.extend(
        InsnrgAppSensor(runtime.app, description)
        for description in APP_SENSORS
        if description.key in app_data
    )

    async_add_entities(entities)


class InsnrgChemistrySensor(InsnrgEntity, SensorEntity):
    """Live pH or ORP reading."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, key_suffix="reading")
        name, unit, device_class = PH_ORP_SENSORS[device_id]
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

    @property
    def native_value(self) -> float | None:
        """Return the current reading."""
        return as_float((self.device.get("thermostat") or {}).get("value"))


class InsnrgWaterTempSensor(InsnrgEntity, SensorEntity):
    """Measured water temperature."""

    _attr_name = "Water temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, key_suffix="water_temp")

    @property
    def native_value(self) -> float | None:
        """Return the water temperature."""
        return as_float((self.device.get("temperature") or {}).get("value"))


class InsnrgAppSensor(InsnrgAppEntity, SensorEntity):
    """A maintenance counter from the app API dashboard."""

    entity_description: InsnrgAppSensorDescription

    def __init__(
        self,
        coordinator: InsnrgAppCoordinator,
        description: InsnrgAppSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the counter value."""
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the service-life ceiling where the API reports one."""
        entry = (self.coordinator.data or {}).get(self.entity_description.key) or {}
        maximum = entry.get("max")
        return {"service_life_hours": maximum} if maximum else None
