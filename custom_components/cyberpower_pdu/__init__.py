from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, PLATFORMS
from .coordinator import CyberPowerPduCoordinator

type CyberPowerPduConfigEntry = ConfigEntry[CyberPowerPduCoordinator]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version == 1:
        _remove_removed_entities(hass, entry)
        _remove_disabled_by_default_cycle_buttons(hass, entry)
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CyberPowerPduConfigEntry) -> bool:
    coordinator = CyberPowerPduCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _remove_removed_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_removed_entities(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CyberPowerPduConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_close()
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant,
    entry: CyberPowerPduConfigEntry,
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _remove_removed_entities(hass: HomeAssistant, entry: CyberPowerPduConfigEntry) -> None:
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if entity_entry.entity_id.startswith("select.") and entity_entry.entity_id.endswith(
            "_power_cycle_outlet"
        ):
            registry.async_remove(entity_entry.entity_id)
        elif (
            unique_id
            and "_outlet_" not in unique_id
            and unique_id.endswith("_power_cycle_selected_outlet")
        ):
            registry.async_remove(entity_entry.entity_id)
        elif unique_id and unique_id.endswith(
            ("_power_cycle_outlet", "_power_cycle_selected_outlet")
        ):
            registry.async_remove(entity_entry.entity_id)


def _remove_disabled_by_default_cycle_buttons(
    hass: HomeAssistant, entry: CyberPowerPduConfigEntry
) -> None:
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if (
            unique_id
            and entity_entry.entity_id.startswith("button.")
            and "_outlet_" in unique_id
            and unique_id.endswith("_power_cycle")
        ):
            registry.async_remove(entity_entry.entity_id)
