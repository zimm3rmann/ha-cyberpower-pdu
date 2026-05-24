from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from . import CyberPowerPduConfigEntry
from .entity import CyberPowerPduEntity
from .snmp import CyberPowerPduData

LEGACY_OUTLET_SENSOR_KEYS = (
    "power",
    "apparent_power",
    "current",
    "energy",
    "peak_power",
)


@dataclass(frozen=True, kw_only=True)
class PduSensorDescription(SensorEntityDescription):
    value_fn: Callable[[CyberPowerPduData], int | float | None]


PDU_SENSORS: tuple[PduSensorDescription, ...] = (
    PduSensorDescription(
        key="total_power",
        name="Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power,
    ),
    PduSensorDescription(
        key="total_apparent_power",
        name="Apparent Power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.apparent_power,
    ),
    PduSensorDescription(
        key="total_current",
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.current,
    ),
    PduSensorDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.voltage,
    ),
    PduSensorDescription(
        key="total_energy",
        name="Energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.energy,
    ),
)


async def async_setup_entry(
    hass,
    entry: CyberPowerPduConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    _remove_legacy_outlet_sensors(hass, entry)
    async_add_entities(
        CyberPowerPduSensor(coordinator, description) for description in PDU_SENSORS
    )


class CyberPowerPduSensor(CyberPowerPduEntity, SensorEntity):
    entity_description: PduSensorDescription

    def __init__(self, coordinator, description: PduSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.device_identifier}_{description.key}"

    @property
    def native_value(self) -> int | float | None:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None


def _remove_legacy_outlet_sensors(hass, entry: CyberPowerPduConfigEntry) -> None:
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity_entry.entity_id.startswith("sensor.") and _is_legacy_outlet_sensor(
            entity_entry.unique_id
        ):
            registry.async_remove(entity_entry.entity_id)


def _is_legacy_outlet_sensor(unique_id: str | None) -> bool:
    return bool(
        unique_id
        and "_outlet_" in unique_id
        and any(unique_id.endswith(f"_{key}") for key in LEGACY_OUTLET_SENSOR_KEYS)
    )
