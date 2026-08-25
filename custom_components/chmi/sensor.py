from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, MAX_DATA_AGE
from .coordinator import ChmiConfigEntry, ChmiDataCoordinator


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
        key="dew_point",
        translation_key="dew_point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="apparent_temperature",
        translation_key="apparent_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="pressure_trend_3h",
        translation_key="pressure_trend_3h",
        # Rozdíl tlaku, ne absolutní hodnota — proto bez device_class.
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # Desetiminutový úhrn sám o sobě entitu nemá — je to tatáž veličina jako
    # intenzita srážek, jen v mm/10 min. Zůstává interně v datech (živí intenzitu
    # a je vidět v diagnostice).
    ChmiSensorDescription(
        key="precipitation_intensity",
        translation_key="precipitation_intensity",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="precipitation_1h",
        translation_key="precipitation_1h",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="precipitation_24h",
        translation_key="precipitation_24h",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    # Denní úhrn počítaný z API řady, takže přežije restart i výpadek pollingu.
    ChmiSensorDescription(
        key="precipitation_today",
        translation_key="precipitation_today",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="sunshine_today",
        translation_key="sunshine_today",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
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
        entity_registry_enabled_default=False,
    ),
    ChmiSensorDescription(
        key="wind_gust_max_24h",
        translation_key="wind_gust_max_24h",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    ChmiSensorDescription(
        key="wind_direction",
        translation_key="wind_direction",
        native_unit_of_measurement=DEGREE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    ChmiSensorDescription(
        key="wind_gust_direction",
        translation_key="wind_gust_direction",
        native_unit_of_measurement=DEGREE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    # Teplotní extrémy jsou jen denní. Klouzavé 24h okno u teploty nefunguje:
    # maximum by do odpoledne hlásilo včerejší vrchol a minimum by za běžného
    # denního chodu vycházelo shodně s denním (naměřeno 141 z 141 vzorků), jinak
    # by ukazovalo včerejší chladno. U nárazů větru a srážek klouzavé okno smysl
    # dává — ty se na denní chod nevážou.
    # Přes název „today“ je to MEASUREMENT, ne TOTAL_INCREASING —
    # dlouhodobá statistika má u teploty ukládat min/průměr/max za hodinu,
    # kdežto TOTAL_INCREASING by z ní počítal nesmyslný kumulativní součet.
    ChmiSensorDescription(
        key="temperature_min_today",
        translation_key="temperature_min_today",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChmiSensorDescription(
        key="temperature_max_today",
        translation_key="temperature_max_today",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChmiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(ChmiSensor(coordinator, desc) for desc in SENSORS)


class ChmiSensor(CoordinatorEntity[ChmiDataCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

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
    def available(self) -> bool:
        """Dostupné, dokud máme hodnotu a stanice není dlouho zticha.

        Jeden selhaný poll neudělá díru v grafu (okamžité veličiny se drží
        z minula), ale mlčící stanice se po MAX_DATA_AGE přizná.
        """
        data = self.coordinator.data
        if not data or data.get(self.entity_description.key) is None:
            return False
        last = data.get("last_measurement")
        if last is not None and dt_util.utcnow() - last > MAX_DATA_AGE:
            return False
        return True

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {
            "station_id": self.coordinator.station_id,
            "station_name": self.coordinator.station_name,
        }
        last = data.get("last_measurement")
        if last is not None:
            attrs["last_measurement"] = last.isoformat()

        # Směr větru visí na entitě rychlosti, aby byl vidět i bez zapnutí
        # samostatné entity směru.
        if self.entity_description.key == "wind_speed":
            degrees = data.get("wind_direction")
            if degrees is not None:
                attrs["direction"] = degrees
            cardinal = data.get("wind_direction_cardinal")
            if cardinal is not None:
                attrs["cardinal"] = cardinal
        return attrs
