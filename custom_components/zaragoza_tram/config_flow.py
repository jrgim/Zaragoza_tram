from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, PARADAS

class ZaragozaTramConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Primer paso: elegir tranvía o bus."""
        if user_input is not None:
            if user_input["tipo"] == "Tranvía":
                return await self.async_step_tram()
            return await self.async_step_bus()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("tipo", default="Tranvía"): vol.In(["Tranvía", "Bus"]),
            }),
        )

    async def async_step_tram(self, user_input=None):
        """Configuración de parada de tranvía (comportamiento original)."""
        errors = {}

        if user_input is not None:
            stop_name = user_input["stop_name"]
            stop_id = next(id for id, name in PARADAS if name == stop_name)

            return self.async_create_entry(
                title=f"Parada {stop_name}",
                data={"tipo": "tram", "stop_id": stop_id, "stop_name": stop_name},
            )

        nombres_paradas = list({name for _, name in PARADAS})

        return self.async_show_form(
            step_id="tram",
            data_schema=vol.Schema({
                vol.Required("stop_name"): vol.In(nombres_paradas),
            }),
            errors=errors,
        )

    async def async_step_bus(self, user_input=None):
        """Configuración de poste de bus: número de marquesina + línea opcional."""
        errors = {}

        if user_input is not None:
            poste = user_input["poste"].strip()
            linea = user_input.get("linea", "").strip().upper()

            if not poste.isdigit():
                errors["base"] = "invalid_poste"
            else:
                await self.async_set_unique_id(f"bus_{poste}_{linea}" if linea else f"bus_{poste}")
                self._abort_if_unique_id_configured()

                title = f"Bus poste {poste}"
                if linea:
                    title += f" (línea {linea})"
                return self.async_create_entry(
                    title=title,
                    data={"tipo": "bus", "poste": poste, "linea": linea},
                )

        return self.async_show_form(
            step_id="bus",
            data_schema=vol.Schema({
                vol.Required("poste"): str,
                vol.Optional("linea", default=""): str,
            }),
            errors=errors,
        )
