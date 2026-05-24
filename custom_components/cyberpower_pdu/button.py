from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from . import CyberPowerPduConfigEntry
from .entity import CyberPowerPduEntity


async def async_setup_entry(
    hass,
    entry: CyberPowerPduConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    _remove_consolidated_button(hass, entry)
    _categorize_cycle_buttons(hass, entry)
    entities: list[ButtonEntity] = []
    if coordinator.data:
        entities.extend(
            CyberPowerOutletPowerCycleButton(coordinator, outlet.index, outlet.name)
            for outlet in coordinator.data.outlets
        )
    async_add_entities(entities)
    _categorize_cycle_buttons(hass, entry)


class CyberPowerOutletPowerCycleButton(CyberPowerPduEntity, ButtonEntity):
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, index: int, outlet_name: str) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_name = f"{outlet_name} Power Cycle"
        self._attr_unique_id = f"{coordinator.device_identifier}_outlet_{index}_power_cycle"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.outlet(self._index) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        return {
            "outlet_index": self._index,
        }

    async def async_press(self) -> None:
        await self.coordinator.async_power_cycle_outlet(self._index)


def _remove_consolidated_button(hass, entry: CyberPowerPduConfigEntry) -> None:
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity_entry.entity_id.startswith("button.")
            and entity_entry.unique_id
            and (
                entity_entry.unique_id.endswith("_power_cycle_selected_outlet")
                or (
                    "_outlet_" not in entity_entry.unique_id
                    and entity_entry.entity_id.endswith("_power_cycle")
                )
            )
        ):
            registry.async_remove(entity_entry.entity_id)


def _categorize_cycle_buttons(hass, entry: CyberPowerPduConfigEntry) -> None:
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity_entry.entity_id.startswith("button.")
            and entity_entry.unique_id
            and "_outlet_" in entity_entry.unique_id
            and entity_entry.unique_id.endswith("_power_cycle")
            and entity_entry.entity_category != EntityCategory.CONFIG
        ):
            registry.async_update_entity(
                entity_entry.entity_id,
                entity_category=EntityCategory.CONFIG,
            )
