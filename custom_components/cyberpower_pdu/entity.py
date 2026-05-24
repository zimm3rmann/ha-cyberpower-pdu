from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_NAME, DOMAIN
from .coordinator import CyberPowerPduCoordinator


class CyberPowerPduEntity(CoordinatorEntity[CyberPowerPduCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: CyberPowerPduCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data
        device = data.device if data else None
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_identifier)},
            manufacturer="CyberPower",
            model=(device.model if device else None) or "PDU41001",
            name=(device.name if device else None) or DEVICE_NAME,
            serial_number=device.serial if device else None,
            sw_version=device.firmware if device else None,
            hw_version=device.hardware if device else None,
            configuration_url=f"http://{device.host}" if device else None,
        )
