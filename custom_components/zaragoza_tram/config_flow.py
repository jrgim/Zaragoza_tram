import re
import unicodedata

from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from .api_utils import fetch_json_con_reintentos
from .const import DOMAIN, PARADAS, BUS_API_URL, BUS_LISTADO_URL

RE_PARADA = re.compile(r"^(?:PA)?0*(\d+)$", re.IGNORECASE)
RE_CODIGO_BUSQUEDA = re.compile(r"^PA\s*0*(\d+)$", re.IGNORECASE)
RE_TITULO = re.compile(r"^\((?P<id>[^)]+)\)\s*(?P<resto>.+)$")


def _normalizar(texto):
    """Quita tildes/diacríticos y pasa a minúsculas, para que la búsqueda no
    distinga 'clinico' de 'clínico'."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()

MAX_RESULTADOS_BUSQUEDA = 30

MODO_COMBINADO = "Próximo y siguiente (cualquier línea)"
MODO_POR_LINEA = "Una entidad por línea"

BUSQUEDA_MANUAL = "Ya sé el código de la parada"
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
        """Buscar la parada escribiendo parte de la dirección (o una línea)."""
        errors = {}

        if user_input is not None:
            query_raw = user_input.get("query", "").strip()
            postes = await self.hass.async_add_executor_job(self._fetch_todas_paradas)

            if not postes:
                errors["base"] = "listado_no_disponible"
            else:
                match_codigo = RE_CODIGO_BUSQUEDA.match(query_raw)
                if match_codigo:
                    # Ha escrito el código oficial de la marquesina (PA00100):
                    # buscamos coincidencia exacta por id, no por texto.
                    codigo = match_codigo.group(1)
                    encontrada = next(
                        (p for p in postes if p["id"].replace("tuzsa-", "") == codigo), None
                    )
                    if encontrada:
                        self._parada = codigo
                        return await self.async_step_bus_linea()
                    errors["base"] = "sin_resultados"
                else:
                    query = _normalizar(query_raw)
                    coincidencias = sorted(
                        (p for p in postes if query in _normalizar(p["title"])),
                        key=self._etiqueta,
                    )
                    if not coincidencias:
                        errors["base"] = "sin_resultados"
                    elif len(coincidencias) > MAX_RESULTADOS_BUSQUEDA:
                        errors["base"] = "demasiados_resultados"
                    elif len(coincidencias) == 1:
                        self._parada = coincidencias[0]["id"].replace("tuzsa-", "")
                        return await self.async_step_bus_linea()
                    else:
                        self._opciones_busqueda = {
                            self._etiqueta(p): p["id"].replace("tuzsa-", "") for p in coincidencias
                        }
                        return await self.async_step_bus_buscar_resultados()

        return self.async_show_form(
            step_id="bus_buscar",
            data_schema=vol.Schema({
                vol.Required("query"): str,
            }),
            errors=errors,
        )

    async def async_step_bus_buscar_resultados(self, user_input=None):
        """Elegir una parada concreta entre las coincidencias de la búsqueda."""
        if user_input is not None:
            self._parada = self._opciones_busqueda.get(user_input["parada_busqueda"])
            if self._parada:
                return await self.async_step_bus_linea()

        return self.async_show_form(
            step_id="bus_buscar_resultados",
            data_schema=vol.Schema({
                vol.Required("parada_busqueda"): vol.In(list(self._opciones_busqueda.keys())),
            }),
        )

    @staticmethod
    def _etiqueta(poste):
        """Reordena '(100) Av. Ejemplo Líneas: 10' a 'Av. Ejemplo Líneas: 10 [100]'
        para que la dirección quede primero (y así se pueda ordenar/leer por calle)."""
        match = RE_TITULO.match(poste["title"])
        if not match:
            return poste["title"]
        return f"{match.group('resto')} [{match.group('id')}]"

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
    @callback
    def async_get_options_flow(config_entry):
        return ZaragozaTramOptionsFlow()

    @staticmethod
    def _fetch_lineas(parada):
        data = fetch_json_con_reintentos(BUS_API_URL.format(poste=parada), timeout=10)
        if data is None:
            return []
        return sorted({d.get("linea") for d in data.get("destinos", []) if d.get("linea")})

    @staticmethod
    def _fetch_todas_paradas():
        data = fetch_json_con_reintentos(BUS_LISTADO_URL)
        if data is None:
            return []
        return [p for p in data.get("result", []) if p.get("id") and p.get("title")]


class ZaragozaTramOptionsFlow(config_entries.OptionsFlow):
    """Permite cambiar la línea o el modo de una entrada de bus ya creada,
    sin tener que borrarla y volver a añadirla."""

    async def async_step_init(self, user_input=None):
        entry = self.config_entry
        if entry.data.get("tipo") != "bus":
            return self.async_abort(reason="solo_bus")

        if user_input is not None:
            linea = user_input.get("linea", "").strip().upper()
            self._nuevos_datos = dict(entry.data)

            if linea:
                self._nuevos_datos.update({"linea": linea, "modo": "combinado"})
                self._nuevos_datos.pop("lineas", None)
                return self._guardar()

            # Sin línea concreta: preguntamos el modo, igual que en el alta.
            return await self.async_step_modo()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("linea", default=entry.data.get("linea", "")): str,
            }),
            description_placeholders={"parada": entry.data.get("parada", "")},
        )

    async def async_step_modo(self, user_input=None):
        entry = self.config_entry

        if user_input is not None:
            self._nuevos_datos["linea"] = ""
            if user_input["modo"] == MODO_POR_LINEA:
                lineas = await self.hass.async_add_executor_job(
                    ZaragozaTramConfigFlow._fetch_lineas, entry.data["parada"]
                )
                if lineas:
                    self._nuevos_datos.update({"modo": "por_linea", "lineas": lineas})
                else:
                    self._nuevos_datos.update({"modo": "combinado"})
                    self._nuevos_datos.pop("lineas", None)
            else:
                self._nuevos_datos.update({"modo": "combinado"})
                self._nuevos_datos.pop("lineas", None)
            return self._guardar()

        modo_actual = MODO_POR_LINEA if entry.data.get("modo") == "por_linea" else MODO_COMBINADO
        return self.async_show_form(
            step_id="modo",
            data_schema=vol.Schema({
                vol.Required("modo", default=modo_actual): vol.In(
                    [MODO_COMBINADO, MODO_POR_LINEA]
                ),
            }),
        )

    def _guardar(self):
        self.hass.config_entries.async_update_entry(self.config_entry, data=self._nuevos_datos)
        return self.async_create_entry(title="", data={})
