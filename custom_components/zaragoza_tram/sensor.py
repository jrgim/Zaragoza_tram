import requests
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN, API_URL

async def async_setup_entry(hass, entry, async_add_entities):
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