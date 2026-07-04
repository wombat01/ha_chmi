from __future__ import annotations

from homeassistant import config_entries
import voluptuous as vol

from .const import CONF_STATION_ID, DEFAULT_STATION_ID, DOMAIN


class ChmiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID].strip().upper()
            await self.async_set_unique_id(station_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"ČHMÚ {station_id}",
                data={CONF_STATION_ID: station_id},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATION_ID, default=DEFAULT_STATION_ID): str}
            ),
            errors=errors,
        )
