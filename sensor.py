from __future__ import annotations

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
    PERCENTAGE,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChmiDataCoordinator

# Cardinal wind directions in Czech (16-point compass)
_CARDINAL_CS = [
    "S",
    "SSV",
    "SV",
    "VSV",
    "V",
    "VJV",
    "JV",
    "JJV",
    "J",
    "JJZ",
    "JZ",
    "ZJZ",
    "Z",
    "ZSZ",
    "SZ",
    "SSZ",
]


def _degrees_to_cardinal(degrees: float) -> str:
    return _CARDINAL_CS[round(degrees / 22.5) % 16]


@dataclass(frozen=True, kw_only=True)
class ChmiSensorDescription(SensorEntityDescription):
    pass


SENSORS: list[ChmiSensorDescription] = [
    ChmiSensorDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    ChmiSensorDescription(
        key="pressure",
        translation_key="pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="precipitation",
        translation_key="precipitation",
        native_unit_of_measurement="mm",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="sunshine",
        translation_key="sunshine",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    ChmiSensorDescription(
        key="wind_speed",
        translation_key="wind_speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="wind_gust",
        translation_key="wind_gust",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="wind_direction",
        translation_key="wind_direction",
        native_unit_of_measurement="\u00b0",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ChmiDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ChmiSensor(coordinator, desc) for desc in SENSORS)


class ChmiSensor(CoordinatorEntity[ChmiDataCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ChmiDataCoordinator,
        description: ChmiSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        station_slug = coordinator.station_id.lower()
        self._attr_unique_id = f"chmi_{station_slug}_{description.key}"
        self._attr_suggested_object_id = f"chmi_{station_slug}_{description.key}"

    @property
    def native_value(self) -> float | str | None:
        if self.entity_description.key == "wind_direction_cardinal":
            val = self.coordinator.data.get("wind_direction")
            return _degrees_to_cardinal(val) if val is not None else None
        val = self.coordinator.data.get(self.entity_description.key)
        if val is None:
            return None
        if self.entity_description.key == "precipitation":
            return round(val, 2)
        return round(val, 1)

    @property
    def device_info(self) -> DeviceInfo:
        station_slug = (
            f"{self.coordinator.station_id.lower()}-"
            f"{self.coordinator.station_name.lower().replace(' ', '-')}"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.station_id)},
            name=self.coordinator.station_name,
            manufacturer="ČHMÚ",
            model=self.coordinator.station_id,
            configuration_url=f"https://www.chmi.cz/w/{station_slug}",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "station_id": self.coordinator.station_id,
            "station_name": self.coordinator.station_name,
        }
        if self.coordinator.latitude is not None:
            attrs["latitude"] = self.coordinator.latitude
            attrs["longitude"] = self.coordinator.longitude
        if self.coordinator.altitude is not None:
            attrs["altitude"] = self.coordinator.altitude
        return attrs
