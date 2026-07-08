import re
import requests
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN, API_URL, BUS_API_URL

RE_MINUTOS = re.compile(r"(\d+)\s*min", re.IGNORECASE)


def parse_minutos(texto):
    """'12 minutos.' -> 12 | 'En la parada.' -> 0 | otro -> None."""
    if not texto:
        return None
    if "parada" in texto.lower():
        return 0
    match = RE_MINUTOS.search(texto)
    return int(match.group(1)) if match else None


async def async_setup_entry(hass, entry, async_add_entities):
    tipo = entry.data.get("tipo", "tram")  # entradas antiguas no tienen "tipo"

    if tipo == "bus":
        parada = entry.data["parada"]
        modo = entry.data.get("modo", "combinado")

        if modo == "por_linea":
            entities = []
            for linea in entry.data.get("lineas", []):
                entities.append(ZaragozaBusSensor(parada, linea, 1))
                entities.append(ZaragozaBusSensor(parada, linea, 2))
            async_add_entities(entities)
        else:
            linea = entry.data.get("linea") or None
            async_add_entities([
                ZaragozaBusSensor(parada, linea, 1),
                ZaragozaBusSensor(parada, linea, 2),
            ])
    else:
        stop_id = entry.data.get("stop_id")
        stop_name = entry.data.get("stop_name")
        async_add_entities([
            ZaragozaTramSensor(stop_id, stop_name, 1),
            ZaragozaTramSensor(stop_id, stop_name, 2)
        ])


class ZaragozaTramSensor(SensorEntity):
    def __init__(self, stop_id, stop_name, tram_number):
        self._stop_id = stop_id
        self._stop_name = stop_name
        self._tram_number = tram_number
        self._state = None
        self._name = f"Tranvía {tram_number} - {stop_name}"
        self._attr_icon = "mdi:tram"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    def update(self):
        response = requests.get(API_URL)

        if response.status_code == 200:
            data = response.json()
            stops = data.get("result", [])

            # Find the stop with the given ID
            stop_data = next((stop for stop in stops if str(stop["id"]) == str(self._stop_id)), None)

            if stop_data:
                arrivals = stop_data.get("destinos", [])
                if arrivals:
                    self._state = arrivals[self._tram_number - 1].get("minutos")
                else:
                    self._state = "Sin datos"
            else:
                self._state = "Parada no encontrada"
        else:
            self._state = "Error al conectar"


class ZaragozaBusSensor(SensorEntity):
    """Bus N (1=próximo, 2=siguiente) en una parada, opcionalmente filtrado por línea.

    Sin filtro de línea, "próximo"/"siguiente" son las dos llegadas más
    cercanas de CUALQUIER línea que pase por la parada (no siempre coinciden
    con el "primero"/"segundo" de una única línea): la API devuelve las
    líneas en un orden que no está garantizado que sea por tiempo de llegada.
    """

    _attr_icon = "mdi:bus"
    _attr_native_unit_of_measurement = "min"

    def __init__(self, parada, linea, bus_number):
        self._parada = parada
        self._linea = linea
        self._bus_number = bus_number
        self._state = None
        self._attrs = {}
        self._etiqueta = "próximo" if bus_number == 1 else "siguiente"

        if linea:
            self._name = f"Bus {linea} {self._etiqueta} - Parada {parada}"
            self._attr_unique_id = f"{DOMAIN}_bus_{parada}_{linea}_{bus_number}"
        else:
            # Sin línea fija: el nombre se actualizará en cada update() con
            # la línea del bus que realmente resulte ser el próximo/siguiente.
            self._name = f"Bus {self._etiqueta} - Parada {parada}"
            self._attr_unique_id = f"{DOMAIN}_bus_{parada}_{bus_number}"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs

    def update(self):
        try:
            response = requests.get(BUS_API_URL.format(poste=self._parada), timeout=15)
        except requests.RequestException:
            # La API del SAE falla a menudo: conservamos el último dato
            return

        if response.status_code != 200:
            return

        try:
            data = response.json()
        except ValueError:
            return

        destinos = data.get("destinos", [])

        if self._linea:
            destinos = [d for d in destinos if d.get("linea", "").upper() == self._linea]
            if not destinos:
                self._state = None
                return
            destino = destinos[0]
            campo = "primero" if self._bus_number == 1 else "segundo"
            self._set_state(data, destino, campo)
            return

        # Sin filtro: mezclamos las llegadas (primero y segundo) de todas
        # las líneas de la parada y nos quedamos con la N-ésima más cercana.
        llegadas = []
        for destino in destinos:
            for campo in ("primero", "segundo"):
                minutos = parse_minutos(destino.get(campo))
                if minutos is not None:
                    llegadas.append((minutos, destino, campo))

        llegadas.sort(key=lambda item: item[0])

        if len(llegadas) < self._bus_number:
            self._state = None
            return

        minutos, destino, campo = llegadas[self._bus_number - 1]
        self._state = minutos
        linea_encontrada = destino.get("linea")
        if linea_encontrada:
            self._name = f"Bus {linea_encontrada} {self._etiqueta} - Parada {self._parada}"
        self._attrs = {
            "parada": data.get("title"),
            "linea": linea_encontrada,
            "destino": destino.get("destino"),
            "texto_original": destino.get(campo),
            "ultima_actualizacion_api": data.get("lastUpdated"),
        }

    def _set_state(self, data, destino, campo):
        self._state = parse_minutos(destino.get(campo))
        self._attrs = {
            "parada": data.get("title"),
            "linea": destino.get("linea"),
            "destino": destino.get("destino"),
            "texto_original": destino.get(campo),
            "ultima_actualizacion_api": data.get("lastUpdated"),
        }
