import time

import requests


def fetch_json_con_reintentos(url, timeout=15, intentos=3, espera=1):
    """Pide JSON a `url`, reintentando si falla.

    La API del SAE de Avanza (usada para los postes de bus) falla peticiones
    a menudo con timeouts o errores transitorios. Devuelve None si todos los
    intentos fallan, en vez de propagar la excepción.
    """
    for intento in range(intentos):
        try:
            response = requests.get(url, timeout=timeout)
        except requests.RequestException:
            response = None

        if response is not None and response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return None

        if intento < intentos - 1:
            time.sleep(espera)

    return None
