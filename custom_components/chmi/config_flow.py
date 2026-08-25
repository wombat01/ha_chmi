from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_STATION_ID, CONF_STATION_NAME, DEFAULT_STATION_ID, DOMAIN
from .coordinator import async_fetch_station_info

_LOGGER = logging.getLogger(__name__)


class ChmiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        station_id = DEFAULT_STATION_ID

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID].strip().upper()
            await self.async_set_unique_id(station_id)
            self._abort_if_unique_id_configured()

            info = await self._async_station_info(station_id, errors)
            if info is not None:
                # Statické údaje uložíme rovnou — koordinátor pak 200kB detail
                # stanice nemusí stahovat vůbec.
                return self.async_create_entry(
                    title=f"ČHMÚ {info[CONF_STATION_NAME]}",
                    data={CONF_STATION_ID: station_id, **info},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATION_ID, default=station_id): str}
            ),
            errors=errors,
        )

    async def _async_station_info(
        self, station_id: str, errors: dict[str, str]
    ) -> dict[str, Any] | None:
        """Ověř stanici proti API; při chybě vyplní errors a vrátí None."""
        try:
            return await async_fetch_station_info(self.hass, station_id)
        except aiohttp.ClientResponseError as err:
            errors["base"] = "invalid_station" if err.status == 404 else "cannot_connect"
        except (aiohttp.ClientError, asyncio.TimeoutError):
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001 — konfigurační dialog nesmí spadnout
            _LOGGER.exception("Neočekávaná chyba při ověřování stanice %s", station_id)
            errors["base"] = "unknown"
        return None
