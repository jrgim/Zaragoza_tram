import re

from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, PARADAS

RE_PARADA = re.compile(r"^(?:PA)?0*(\d+)$", re.IGNORECASE)

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
        """Configuración de parada de bus: código de parada + línea opcional."""
        errors = {}

        if user_input is not None:
            parada_raw = user_input["parada"].strip()
            linea = user_input.get("linea", "").strip().upper()

            match = RE_PARADA.match(parada_raw)
            if not match:
                errors["base"] = "invalid_parada"
            else:
                parada = match.group(1)
                await self.async_set_unique_id(f"bus_{parada}_{linea}" if linea else f"bus_{parada}")
                self._abort_if_unique_id_configured()

                title = f"Bus parada {parada}"
                if linea:
                    title += f" (línea {linea})"
                return self.async_create_entry(
                    title=title,
                    data={"tipo": "bus", "parada": parada, "linea": linea},
                )

        return self.async_show_form(
            step_id="bus",
            data_schema=vol.Schema({
                vol.Required("parada"): str,
                vol.Optional("linea", default=""): str,
            }),
            errors=errors,
        )
