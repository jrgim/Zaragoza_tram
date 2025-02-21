from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, PARADAS

class ZaragozaTramConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Obtain ID from the selected name
            stop_name = user_input["stop_name"]
            stop_id = next(id for id, name in PARADAS if name == stop_name)
            
            return self.async_create_entry(
                title=f"Parada {stop_name}",
                data={"stop_id": stop_id, "stop_name": stop_name},
            )

        # Only names for the user to select
        nombres_paradas = list({name for _, name in PARADAS})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("stop_name"): vol.In(nombres_paradas),
            }),
            errors=errors,
        )