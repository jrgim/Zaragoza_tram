import threading
import time

import requests

_cache_lock = threading.Lock()
_cache = {}  # url -> (timestamp, data)


def fetch_json_con_reintentos(url, timeout=15, intentos=3, espera=1, cache_ttl=0):
    """Pide JSON a `url`, reintentando si falla.

    La API del SAE de Avanza (usada para los postes de bus) falla peticiones
    a menudo con timeouts o errores transitorios. Devuelve None si todos los
    intentos fallan, en vez de propagar la excepción.

    Si `cache_ttl` > 0, reutiliza la última respuesta para esa misma `url` si
    tiene menos de `cache_ttl` segundos: cuando varios sensores de la misma
    parada (próximo/siguiente, o una entidad por línea) piden la misma URL en
    el mismo ciclo de sondeo, solo el primero llega a hacer la petición real.
    """
    if cache_ttl:
        with _cache_lock:
            cached = _cache.get(url)
        if cached and time.time() - cached[0] < cache_ttl:
            return cached[1]

    for intento in range(intentos):
        try:
            response = requests.get(url, timeout=timeout)
        except requests.RequestException:
            response = None

        if response is not None and response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                return None
            if cache_ttl:
                with _cache_lock:
                    _cache[url] = (time.time(), data)
            return data

        if intento < intentos - 1:
            time.sleep(espera)

    return None
