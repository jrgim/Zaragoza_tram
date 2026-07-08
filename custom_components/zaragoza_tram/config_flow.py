import re

import requests
from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, PARADAS, BUS_API_URL, BUS_LISTADO_URL

RE_PARADA = re.compile(r"^(?:PA)?0*(\d+)$", re.IGNORECASE)

MODO_COMBINADO = "Próximo y siguiente (cualquier línea)"
MODO_POR_LINEA = "Una entidad por línea"

BUSQUEDA_MANUAL = "Ya sé el código de la parada (PA00239, poste, etc.)"
BUSQUEDA_LISTADO = "Buscar la parada en el listado"

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
        """Primer paso de bus: cómo identificar la parada."""
        if user_input is not None:
            if user_input["busqueda"] == BUSQUEDA_LISTADO:
                return await self.async_step_bus_buscar()
            return await self.async_step_bus_manual()

        return self.async_show_form(
            step_id="bus",
            data_schema=vol.Schema({
                vol.Required("busqueda", default=BUSQUEDA_LISTADO): vol.In(
                    [BUSQUEDA_LISTADO, BUSQUEDA_MANUAL]
                ),
            }),
        )

    async def async_step_bus_manual(self, user_input=None):
        """Configuración de parada de bus: código de parada + línea opcional."""
        errors = {}

        if user_input is not None:
            parada_raw = user_input["parada"].strip()
            linea = user_input.get("linea", "").strip().upper()

            match = RE_PARADA.match(parada_raw)
            if not match:
                errors["base"] = "invalid_parada"
            else:
                self._parada = match.group(1)
                if linea:
                    return await self._create_bus_entry(self._parada, linea)
                # Sin línea concreta: preguntamos cómo quiere los sensores.
                return await self.async_step_bus_mode()

        return self.async_show_form(
            step_id="bus_manual",
            data_schema=vol.Schema({
                vol.Required("parada"): str,
                vol.Optional("linea", default=""): str,
            }),
            errors=errors,
        )

    async def async_step_bus_buscar(self, user_input=None):
        """Buscar la parada por dirección en el listado completo de postes."""
        errors = {}

        if user_input is not None and getattr(self, "_opciones_busqueda", None):
            self._parada = self._opciones_busqueda.get(user_input["parada_busqueda"])
            if self._parada:
                return await self.async_step_bus_linea()
            errors["base"] = "listado_no_disponible"

        postes = await self.hass.async_add_executor_job(self._fetch_todas_paradas)
        if not postes:
            errors["base"] = "listado_no_disponible"
            return self.async_show_form(
                step_id="bus_buscar",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        # Etiqueta legible (incluye dirección y líneas) -> id de poste.
        self._opciones_busqueda = {p["title"]: p["id"].replace("tuzsa-", "") for p in postes}

        return self.async_show_form(
            step_id="bus_buscar",
            data_schema=vol.Schema({
                vol.Required("parada_busqueda"): vol.In(list(self._opciones_busqueda.keys())),
            }),
            errors=errors,
        )

    async def async_step_bus_linea(self, user_input=None):
        """Tras elegir la parada en el listado: línea opcional."""
        if user_input is not None:
            linea = user_input.get("linea", "").strip().upper()
            if linea:
                return await self._create_bus_entry(self._parada, linea)
            return await self.async_step_bus_mode()

        return self.async_show_form(
            step_id="bus_linea",
            data_schema=vol.Schema({
                vol.Optional("linea", default=""): str,
            }),
        )

    async def async_step_bus_mode(self, user_input=None):
        """Sin línea concreta: combinar todas las líneas o una entidad por línea."""
        if user_input is not None:
            if user_input["modo"] == MODO_POR_LINEA:
                return await self._create_bus_entry_por_linea(self._parada)
            return await self._create_bus_entry(self._parada, "")

        return self.async_show_form(
            step_id="bus_mode",
            data_schema=vol.Schema({
                vol.Required("modo", default=MODO_COMBINADO): vol.In(
                    [MODO_COMBINADO, MODO_POR_LINEA]
                ),
            }),
        )

    async def _create_bus_entry(self, parada, linea):
        await self.async_set_unique_id(f"bus_{parada}_{linea}" if linea else f"bus_{parada}_combinado")
        self._abort_if_unique_id_configured()

        title = f"Bus parada {parada}"
        if linea:
            title += f" (línea {linea})"
        return self.async_create_entry(
            title=title,
            data={"tipo": "bus", "parada": parada, "linea": linea, "modo": "combinado"},
        )

    async def _create_bus_entry_por_linea(self, parada):
        await self.async_set_unique_id(f"bus_{parada}_todas")
        self._abort_if_unique_id_configured()

        lineas = await self.hass.async_add_executor_job(self._fetch_lineas, parada)
        if not lineas:
            # No se pudo consultar la API (falla a menudo): caemos al modo
            # combinado en vez de crear una entrada sin ninguna entidad.
            return await self._create_bus_entry(parada, "")

        return self.async_create_entry(
            title=f"Bus parada {parada} (todas las líneas)",
            data={"tipo": "bus", "parada": parada, "linea": "", "modo": "por_linea", "lineas": lineas},
        )

    @staticmethod
    def _fetch_lineas(parada):
        try:
            response = requests.get(BUS_API_URL.format(poste=parada), timeout=10)
        except requests.RequestException:
            return []
        if response.status_code != 200:
            return []
        try:
            data = response.json()
        except ValueError:
            return []
        return sorted({d.get("linea") for d in data.get("destinos", []) if d.get("linea")})

    @staticmethod
    def _fetch_todas_paradas():
        try:
            response = requests.get(BUS_LISTADO_URL, timeout=15)
        except requests.RequestException:
            return []
        if response.status_code != 200:
            return []
        try:
            data = response.json()
        except ValueError:
            return []
        return [p for p in data.get("result", []) if p.get("id") and p.get("title")]
