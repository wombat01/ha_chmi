from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import ChmiConfigEntry, ChmiDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ChmiConfigEntry) -> bool:
    coordinator = ChmiDataCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Dotazy jedou zarovnaně na desetiminutovky ČHMÚ, ne od času startu HA.
    entry.async_on_unload(coordinator.async_start_polling())

    # Aktualizuj název záznamu na skutečné jméno stanice (z API)
    desired_title = f"ČHMÚ {coordinator.station_name}"
    if entry.title != desired_title:
        hass.config_entries.async_update_entry(entry, title=desired_title)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ChmiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
