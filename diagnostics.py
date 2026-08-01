from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import ChmiConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ChmiConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = dict(coordinator.data or {})
    last = data.get("last_measurement")
    if last is not None:
        data["last_measurement"] = last.isoformat()

    return {
        "station": {
            "id": coordinator.station_id,
            "name": coordinator.station_name,
            "latitude": coordinator.latitude,
            "longitude": coordinator.longitude,
            "altitude": coordinator.altitude,
        },
        "last_update_success": coordinator.last_update_success,
        "data": data,
    }
