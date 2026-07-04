from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BASE_HEADERS,
    CONF_STATION_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    URL_CLIMATE,
    URL_PRECIPITATION,
    URL_STATION_DETAIL,
    URL_TEMPERATURE,
    URL_WIND,
)

_LOGGER = logging.getLogger(__name__)


class ChmiDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    station_name: str
    latitude: float | None
    longitude: float | None
    altitude: float | None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.station_id: str = entry.data[CONF_STATION_ID]
        self.station_name = self.station_id
        self.latitude = None
        self.longitude = None
        self.altitude = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.station_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from CHMI API."""
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(
            headers=BASE_HEADERS, timeout=timeout
        ) as session:
            results = await asyncio.gather(
                _fetch_json(session, URL_STATION_DETAIL.format(self.station_id)),
                _fetch_json(session, URL_TEMPERATURE.format(self.station_id)),
                _fetch_json(session, URL_CLIMATE.format(self.station_id)),
                _fetch_json(session, URL_WIND.format(self.station_id)),
                _fetch_json(session, URL_PRECIPITATION.format(self.station_id)),
                return_exceptions=True,
            )

            # Ošetření chyb pro každý request zvlášť
            detail = results[0] if not isinstance(results[0], Exception) else {}
            temp = results[1] if not isinstance(results[1], Exception) else {}
            climate = results[2] if not isinstance(results[2], Exception) else {}
            wind = results[3] if not isinstance(results[3], Exception) else {}
            precip = results[4] if not isinstance(results[4], Exception) else {}

            if not temp and not climate and not wind and not precip:
                raise UpdateFailed(f"Failed to fetch any data for {self.station_id}")

            if detail and isinstance(detail, dict):
                self.station_name = _extract_station_name(detail, self.station_id)
                self.latitude, self.longitude, self.altitude = _extract_coordinates(
                    detail
                )

            return _merge_data_robust(self.data, temp, climate, wind, precip)


async def _fetch_json(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    async with asyncio.timeout(15):
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()


def _extract_station_name(detail: dict[str, Any], station_id: str) -> str:
    add_info = detail.get("addInfo", {}) if isinstance(detail, dict) else {}
    candidates = [
        add_info.get("orpName"),
        detail.get("name") if isinstance(detail, dict) else None,
        detail.get("stationName") if isinstance(detail, dict) else None,
        detail.get("shortName") if isinstance(detail, dict) else None,
        add_info.get("districtName"),
        add_info.get("code"),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return station_id


def _extract_coordinates(
    detail: dict[str, Any],
) -> tuple[float | None, float | None, float | None]:
    if not isinstance(detail, dict):
        return None, None, None
    lat = _to_float(detail.get("lat") or detail.get("latitude"))
    lon = _to_float(detail.get("lon") or detail.get("longitude"))
    alt = _to_float(
        detail.get("altitude") or detail.get("elevation") or detail.get("alt")
    )
    return lat, lon, alt


def _last_point(payload: dict[str, Any]) -> dict[str, Any]:
    points = payload.get("dataPoints", [])
    if not points:
        return {}
    for point in reversed(points):
        if point.get("values"):
            return point
    return points[-1] if points else {}


def _coalesce(*values: Any) -> Any:
    """Return first non-None value — safe for numeric 0."""
    return next((v for v in values if v is not None), None)


def _to_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _merge_data_robust(
    current_data: dict[str, Any] | None,
    temp: dict[str, Any],
    climate: dict[str, Any],
    wind: dict[str, Any],
    precip: dict[str, Any],
) -> dict[str, Any]:
    base = current_data or {
        "temperature": None,
        "humidity": None,
        "pressure": None,
        "precipitation": None,
        "sunshine": None,
        "wind_speed": None,
        "wind_gust": None,
        "wind_direction": None,
    }

    temp_values = _last_point(temp).get("values") or {}
    climate_values = _last_point(climate).get("values") or {}
    wind_values = _last_point(wind).get("values") or {}
    precip_values = _last_point(precip).get("values") or {}

    def _fallback(new_val, old_key):
        return new_val if new_val is not None else base.get(old_key)

    return {
        "temperature": _fallback(_to_float(temp_values.get("T")), "temperature"),
        "humidity": _fallback(_to_float(climate_values.get("H")), "humidity"),
        "pressure": _fallback(_to_float(climate_values.get("P_hm")), "pressure"),
        "precipitation": _fallback(
            _to_float(
                _coalesce(
                    precip_values.get("SRA"),
                    precip_values.get("SRA_10M"),
                    precip_values.get("SRA10M"),
                )
            ),
            "precipitation",
        ),
        "sunshine": _fallback(
            _to_float(
                _coalesce(
                    climate_values.get("SS"),
                    climate_values.get("SS_10M"),
                    climate_values.get("SvitSl"),
                    climate_values.get("SD"),
                    climate_values.get("SunD"),
                )
            ),
            "sunshine",
        ),
        "wind_speed": _fallback(
            _to_float(_coalesce(wind_values.get("F"), wind_values.get("F_mean"))),
            "wind_speed",
        ),
        "wind_gust": _fallback(
            _to_float(_coalesce(wind_values.get("Fmax"), wind_values.get("F_max"))),
            "wind_gust",
        ),
        "wind_direction": _fallback(
            _to_float(_coalesce(wind_values.get("D"), wind_values.get("D_mean"))),
            "wind_direction",
        ),
    }
