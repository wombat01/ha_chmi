from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BASE_HEADERS,
    CARDINALS,
    CONF_ALTITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    EXPECTED_MAX_AGE,
    FRESH_WINDOW,
    KEYS_HUMIDITY,
    KEYS_PRECIPITATION,
    KEYS_PRESSURE,
    KEYS_SUNSHINE,
    KEYS_TEMPERATURE,
    KEYS_WIND_DIR,
    KEYS_WIND_GUST,
    KEYS_WIND_GUST_DIR,
    KEYS_WIND_SPEED,
    POLL_MINUTES,
    POLL_SECOND,
    STALE_RETRY_DELAY,
    URL_CLIMATE,
    URL_STATION_DETAIL,
    URL_WIND,
)

_LOGGER = logging.getLogger(__name__)

# Okamžité veličiny — při výpadku jednoho endpointu se drží poslední známá hodnota,
# aby v grafu nevznikla díra. Kumulativní veličiny se takto přenášet NESMÍ.
_CARRY_FORWARD = (
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_gust",
    "wind_direction",
    "wind_gust_direction",
    "precipitation_1h",
    "precipitation_24h",
    "precipitation_today",
    "sunshine_today",
    "temperature_min_24h",
    "temperature_max_24h",
    "wind_gust_max_24h",
    "pressure_trend_3h",
)

Series = list[tuple[datetime, dict[str, Any]]]

type ChmiConfigEntry = ConfigEntry[ChmiDataCoordinator]


class ChmiDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    station_name: str
    latitude: float | None
    longitude: float | None
    altitude: float | None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.station_id: str = entry.data[CONF_STATION_ID]
        # Statické údaje známe z config entry, pokud už jednou stažené byly.
        self.station_name = entry.data.get(CONF_STATION_NAME) or self.station_id
        self.latitude = entry.data.get(CONF_LATITUDE)
        self.longitude = entry.data.get(CONF_LONGITUDE)
        self.altitude = entry.data.get(CONF_ALTITUDE)
        self._need_detail = CONF_STATION_NAME not in entry.data
        self._retry_unsub: CALLBACK_TYPE | None = None
        self._retry_allowed = True
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.station_id}",
            # Aktualizace řídí zarovnaný plánovač níže, ne pevný interval.
            update_interval=None,
        )

    def _store_station_info(self) -> None:
        """Ulož statické údaje do config entry — příště se detail nestahuje."""
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                CONF_STATION_NAME: self.station_name,
                CONF_LATITUDE: self.latitude,
                CONF_LONGITUDE: self.longitude,
                CONF_ALTITUDE: self.altitude,
            },
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Společné zařízení pro všechny entity stanice."""
        station_slug = (
            f"{self.station_id.lower()}-"
            f"{self.station_name.lower().replace(' ', '-')}"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self.station_id)},
            name=self.station_name,
            manufacturer="ČHMÚ",
            model=self.station_id,
            configuration_url=f"https://www.chmi.cz/w/{station_slug}",
        )

    def async_start_polling(self) -> CALLBACK_TYPE:
        """Naplánuj dotazy na pevné minuty a vrať odhlašovací callback."""
        unsub = async_track_time_change(
            self.hass, self._handle_tick, minute=POLL_MINUTES, second=POLL_SECOND
        )

        def _unsub_all() -> None:
            unsub()
            self._cancel_retry()

        return _unsub_all

    async def _handle_tick(self, now: datetime) -> None:
        self._retry_allowed = True
        await self.async_refresh()

    async def _handle_retry(self, now: datetime) -> None:
        self._retry_unsub = None
        _LOGGER.debug("%s: opakovaný dotaz po chybějící desetiminutovce", self.name)
        await self.async_refresh()

    def _cancel_retry(self) -> None:
        if self._retry_unsub is not None:
            self._retry_unsub()
            self._retry_unsub = None

    async def async_shutdown(self) -> None:
        self._cancel_retry()
        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, Any]:
        """Stáhni řady z ČHMÚ a spočítej z nich odvozené hodnoty."""
        # Sdílená aiohttp session z HA — nezavírá se, session ji spravuje sama.
        session = async_get_clientsession(self.hass)
        now = dt_util.utcnow()

        tasks = [
            _fetch_json(session, URL_CLIMATE.format(self.station_id)),
            _fetch_json(session, URL_WIND.format(self.station_id)),
        ]
        if self._need_detail:
            tasks.append(_fetch_json(session, URL_STATION_DETAIL.format(self.station_id)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        climate = _ok(results[0])
        wind = _ok(results[1])
        detail = _ok(results[2]) if len(results) > 2 else {}

        if not climate and not wind:
            raise UpdateFailed(f"Failed to fetch any data for {self.station_id}")

        if detail:
            self.station_name = _extract_station_name(detail, self.station_id)
            self.latitude, self.longitude, self.altitude = _extract_coordinates(detail)
            # Uložíme jen skutečně zjištěné jméno; jinak to příště zkusíme znovu.
            if self.station_name != self.station_id:
                self._need_detail = False
                self._store_station_info()

        climate_series = _parse_series(climate)
        wind_series = _parse_series(wind)
        data = _build_data(self.data, climate_series, wind_series, now)

        self._cancel_retry()
        last = data.get("last_measurement")
        if self._retry_allowed and (last is None or now - last > EXPECTED_MAX_AGE):
            self._retry_allowed = False
            self._retry_unsub = async_call_later(
                self.hass, STALE_RETRY_DELAY, self._handle_retry
            )

        return data


async def async_fetch_station_info(
    hass: HomeAssistant, station_id: str
) -> dict[str, Any]:
    """Ověř kód stanice a vrať její statické údaje.

    Používá config flow, aby se překlep poznal hned při zadávání. Neexistující
    stanice vrací HTTP 404 → ClientResponseError se stavem 404.
    """
    session = async_get_clientsession(hass)
    detail = await _fetch_json(
        session, URL_STATION_DETAIL.format(station_id), retries=1
    )
    latitude, longitude, altitude = _extract_coordinates(detail)
    return {
        CONF_STATION_NAME: _extract_station_name(detail, station_id),
        CONF_LATITUDE: latitude,
        CONF_LONGITUDE: longitude,
        CONF_ALTITUDE: altitude,
    }


def _ok(result: Any) -> dict[str, Any]:
    """Výsledek jednoho requestu, nebo prázdno když selhal."""
    if isinstance(result, BaseException) or not isinstance(result, dict):
        return {}
    return result


# Timeout se předává per-request, protože sdílená session nemá vlastní.
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=25)


async def _fetch_json(
    session: aiohttp.ClientSession, url: str, *, retries: int = 2
) -> dict[str, Any]:
    """Fetch JSON with retry on transient errors.

    Retries on network/timeout errors and on 429/5xx responses. The CHMI
    provider občas vrací data se špatným Content-Type, proto content_type=None.
    Headers i timeout se předávají per-request kvůli sdílené session.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with session.get(
                url, headers=BASE_HEADERS, timeout=_REQUEST_TIMEOUT
            ) as response:
                # 429/5xx vyhodí ClientResponseError → chytne se níž a retryuje
                response.raise_for_status()
                return await response.json(content_type=None)
        except aiohttp.ClientResponseError as exc:
            # Špatný kód stanice apod. opakováním nespravíme, jen 429 a 5xx.
            if exc.status != 429 and exc.status < 500:
                raise
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            raise
    # Nedosažitelné, ale kvůli typové kontrole:
    raise last_exc if last_exc else RuntimeError("fetch failed")


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


def _leading_float(value: Any) -> float | None:
    """První číslo z textu.

    ČHMÚ vrací polohu jako řetězec, např. y = "50.078 (50° 4' 40.80\\") sš"
    nebo z = "360 m n. m." — čistá číselná pole v odpovědi nejsou.
    """
    if not isinstance(value, str):
        return _to_float(value)
    match = re.search(r"-?\d+(?:[.,]\d+)?", value)
    return _to_float(match.group()) if match else None


def _extract_coordinates(
    detail: dict[str, Any],
) -> tuple[float | None, float | None, float | None]:
    if not isinstance(detail, dict):
        return None, None, None
    lat = _leading_float(_coalesce(detail.get("y"), detail.get("lat"), detail.get("latitude")))
    lon = _leading_float(_coalesce(detail.get("x"), detail.get("lon"), detail.get("longitude")))
    alt = _leading_float(
        _coalesce(detail.get("z"), detail.get("altitude"), detail.get("elevation"))
    )
    return lat, lon, alt


def _parse_series(payload: Any) -> Series:
    """Převeď dataPoints na seřazenou řadu (čas, hodnoty)."""
    if not isinstance(payload, dict):
        return []
    points = payload.get("dataPoints")
    if not isinstance(points, list):
        return []
    series: Series = []
    for point in points:
        if not isinstance(point, dict):
            continue
        values = point.get("values")
        if not isinstance(values, dict) or not values:
            continue
        stamp = dt_util.parse_datetime(str(point.get("timestamp") or ""))
        if stamp is None:
            continue
        series.append((dt_util.as_utc(stamp), values))
    series.sort(key=lambda item: item[0])
    return series


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


def _pick(values: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    return _to_float(_coalesce(*(values.get(key) for key in keys)))


def _latest(series: Series) -> tuple[datetime | None, dict[str, Any]]:
    if not series:
        return None, {}
    stamp, values = series[-1]
    return stamp, values


def _sum_window(
    series: Series, keys: tuple[str, ...], start: datetime, end: datetime
) -> float | None:
    """Úhrn desetiminutovek v intervalu (start, end]."""
    total: float | None = None
    for stamp, values in series:
        if not start < stamp <= end:
            continue
        value = _pick(values, keys)
        if value is None:
            continue
        total = value if total is None else total + value
    return round(total, 2) if total is not None else None


def _sum_today(series: Series, keys: tuple[str, ...]) -> float | None:
    """Úhrn od místní půlnoci.

    Časová značka označuje konec desetiminutovky, takže bod 00:00 patří ještě
    předchozímu dni — proto se datum počítá o sekundu zpět.
    """
    today = dt_util.now().date()
    total: float | None = None
    for stamp, values in series:
        if dt_util.as_local(stamp - timedelta(seconds=1)).date() != today:
            continue
        value = _pick(values, keys)
        if value is None:
            continue
        total = value if total is None else total + value
    return round(total, 2) if total is not None else None


def _extreme_window(
    series: Series, keys: tuple[str, ...], start: datetime, pick_max: bool
) -> float | None:
    best: float | None = None
    for stamp, values in series:
        if stamp < start:
            continue
        value = _pick(values, keys)
        if value is None:
            continue
        if best is None or (value > best if pick_max else value < best):
            best = value
    return best


def _value_near(
    series: Series,
    keys: tuple[str, ...],
    target: datetime,
    tolerance: timedelta = timedelta(minutes=20),
) -> float | None:
    """Hodnota z bodu nejbližšího zadanému času (v rámci tolerance)."""
    best: float | None = None
    best_delta: timedelta | None = None
    for stamp, values in series:
        delta = abs(stamp - target)
        if delta > tolerance:
            continue
        value = _pick(values, keys)
        if value is None:
            continue
        if best_delta is None or delta < best_delta:
            best, best_delta = value, delta
    return best


def dew_point(temperature: float | None, humidity: float | None) -> float | None:
    """Rosný bod podle Magnusovy aproximace."""
    if temperature is None or humidity is None or humidity <= 0:
        return None
    a, b = 17.625, 243.04
    alpha = math.log(humidity / 100) + a * temperature / (b + temperature)
    return round(b * alpha / (a - alpha), 1)


def apparent_temperature(
    temperature: float | None, humidity: float | None, wind_speed: float | None
) -> float | None:
    """Pocitová teplota (australský Apparent Temperature, platí pro teplo i vítr)."""
    if temperature is None or humidity is None:
        return None
    wind = wind_speed or 0.0
    vapour = (humidity / 100) * 6.105 * math.exp(17.27 * temperature / (237.7 + temperature))
    return round(temperature + 0.33 * vapour - 0.70 * wind - 4.00, 1)


def cardinal(degrees: float | None) -> str | None:
    """Směr větru jako zkratka růžice (S, SSV, SV, …)."""
    if degrees is None:
        return None
    return CARDINALS[int((degrees % 360) / 22.5 + 0.5) % 16]


def _build_data(
    current: dict[str, Any] | None,
    climate: Series,
    wind: Series,
    now: datetime,
) -> dict[str, Any]:
    stamp, climate_values = _latest(climate)
    wind_stamp, wind_values = _latest(wind)
    last_measurement = max(
        (item for item in (stamp, wind_stamp) if item is not None), default=None
    )
    # Desetiminutový úhrn platí jen pro svůj interval. Kdyby se přenášel dál,
    # každý další polling by "napršel" znovu a integrace/utility_meter by sčítaly
    # déšť, který nespadl.
    is_fresh = last_measurement is not None and now - last_measurement <= FRESH_WINDOW

    wind_speed = _pick(wind_values, KEYS_WIND_SPEED)
    if wind_speed is None:
        wind_speed = _pick(climate_values, KEYS_WIND_SPEED)
    wind_dir = _pick(wind_values, KEYS_WIND_DIR)
    if wind_dir is None:
        wind_dir = _pick(climate_values, KEYS_WIND_DIR)

    temperature = _pick(climate_values, KEYS_TEMPERATURE)
    humidity = _pick(climate_values, KEYS_HUMIDITY)
    pressure = _pick(climate_values, KEYS_PRESSURE)

    pressure_3h_ago = _value_near(climate, KEYS_PRESSURE, now - timedelta(hours=3))
    pressure_trend = (
        round(pressure - pressure_3h_ago, 1)
        if pressure is not None and pressure_3h_ago is not None
        else None
    )
    sunshine_today = _sum_today(climate, KEYS_SUNSHINE)
    precipitation = _pick(climate_values, KEYS_PRECIPITATION) if is_fresh else None

    data: dict[str, Any] = {
        "temperature": temperature,
        "humidity": humidity,
        "pressure": pressure,
        "precipitation": precipitation,
        # Desetiminutový úhrn přepočtený na hodinovou intenzitu — to je číslo,
        # se kterým se dá porovnávat „slabý/silný déšť“.
        "precipitation_intensity": (
            round(precipitation * 6, 1) if precipitation is not None else None
        ),
        "precipitation_1h": _sum_window(
            climate, KEYS_PRECIPITATION, now - timedelta(hours=1), now
        ),
        "precipitation_24h": _sum_window(
            climate, KEYS_PRECIPITATION, now - timedelta(hours=24), now
        ),
        "precipitation_today": _sum_today(climate, KEYS_PRECIPITATION),
        "sunshine": _pick(climate_values, KEYS_SUNSHINE) if is_fresh else None,
        "sunshine_today": (
            round(sunshine_today / 3600, 2) if sunshine_today is not None else None
        ),
        "wind_speed": wind_speed,
        "wind_gust": _pick(wind_values, KEYS_WIND_GUST),
        "wind_direction": wind_dir,
        "wind_gust_direction": _pick(wind_values, KEYS_WIND_GUST_DIR),
        "wind_gust_max_24h": _extreme_window(
            wind, KEYS_WIND_GUST, now - timedelta(hours=24), pick_max=True
        ),
        "temperature_min_24h": _extreme_window(
            climate, KEYS_TEMPERATURE, now - timedelta(hours=24), pick_max=False
        ),
        "temperature_max_24h": _extreme_window(
            climate, KEYS_TEMPERATURE, now - timedelta(hours=24), pick_max=True
        ),
        "pressure_trend_3h": pressure_trend,
        "last_measurement": last_measurement,
    }

    # Chybějící okamžité hodnoty doplň z minula (výpadek jednoho endpointu).
    if current:
        for key in _CARRY_FORWARD:
            if data.get(key) is None and current.get(key) is not None:
                data[key] = current[key]
        if data["last_measurement"] is None:
            data["last_measurement"] = current.get("last_measurement")

    data["dew_point"] = dew_point(data["temperature"], data["humidity"])
    data["apparent_temperature"] = apparent_temperature(
        data["temperature"], data["humidity"], data["wind_speed"]
    )
    data["wind_direction_cardinal"] = cardinal(data["wind_direction"])
    data["wind_gust_direction_cardinal"] = cardinal(data["wind_gust_direction"])
    return data
