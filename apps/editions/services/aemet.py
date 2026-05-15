import os
import time
import requests
import logging
from django.core.cache import cache
from datetime import date

logger = logging.getLogger(__name__)

# Municipio principal de referencia para el tiempo (Llerena).
# Se reduce a un único municipio para respetar el rate limit de AEMET (~1 req/s).
PRIMARY_TOWN = ("Llerena", "06074")

# Municipios de respaldo, consultados solo si el primario falla.
FALLBACK_TOWNS = [
    ("Berlanga", "06019"),
    ("Fuente del Arco", "06053"),
]

AEMET_BASE = "https://opendata.aemet.es/opendata/api"
REQUEST_TIMEOUT = 8   # segundos por llamada
INTER_REQUEST_DELAY = 1.2   # segundos entre llamadas consecutivas a AEMET


def get_weather_forecast_for_edition(edition_date: date):
    from django.conf import settings
    api_key = getattr(settings, "AEMET_API_KEY", os.environ.get("AEMET_API_KEY", "")).strip()

    if not api_key:
        logger.error("AEMET_API_KEY no configurada.")
        return None

    cache_key = f"aemet_forecast_{edition_date.isoformat()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    headers = {"api_key": api_key, "Accept": "application/json"}

    # Intentamos primero el municipio principal
    result = _fetch_town_forecast(PRIMARY_TOWN[1], PRIMARY_TOWN[0], edition_date, headers)

    if not result:
        # Un solo municipio de respaldo si el principal falla
        for name, code in FALLBACK_TOWNS:
            time.sleep(INTER_REQUEST_DELAY)
            result = _fetch_town_forecast(code, name, edition_date, headers)
            if result:
                break

    if result:
        cache.set(cache_key, result, timeout=3600)

    return result


def _fetch_town_forecast(ine_code: str, town_name: str, edition_date: date, headers: dict):
    """Intenta horaria (17:00) y, si no hay datos, cae a diaria."""

    # ── Horaria ──────────────────────────────────────────────────────────────
    try:
        meta = _aemet_get(
            f"{AEMET_BASE}/prediccion/especifica/municipio/horaria/{ine_code}",
            headers,
        )
        if meta and meta.get("estado") == 200 and meta.get("datos"):
            time.sleep(INTER_REQUEST_DELAY)
            data = _aemet_data(meta["datos"])
            if data:
                dias = data[0].get("prediccion", {}).get("dia", [])
                for dia in dias:
                    if dia.get("fecha", "").startswith(edition_date.isoformat()):
                        parsed = _parse_horaria(dia, "17")
                        if parsed and parsed.get("temperatura") is not None:
                            logger.info("AEMET horaria OK para %s", town_name)
                            return parsed
    except Exception as exc:
        logger.warning("AEMET horaria falló para %s: %s", town_name, exc)

    # ── Diaria (fallback) ─────────────────────────────────────────────────────
    try:
        time.sleep(INTER_REQUEST_DELAY)
        meta = _aemet_get(
            f"{AEMET_BASE}/prediccion/especifica/municipio/diaria/{ine_code}",
            headers,
        )
        if meta and meta.get("estado") == 200 and meta.get("datos"):
            time.sleep(INTER_REQUEST_DELAY)
            data = _aemet_data(meta["datos"])
            if data:
                dias = data[0].get("prediccion", {}).get("dia", [])
                for dia in dias:
                    if dia.get("fecha", "").startswith(edition_date.isoformat()):
                        parsed = _parse_diaria(dia)
                        if parsed and parsed.get("temperatura") is not None:
                            logger.info("AEMET diaria OK para %s", town_name)
                            return parsed
    except Exception as exc:
        logger.warning("AEMET diaria falló para %s: %s", town_name, exc)

    logger.warning("AEMET sin datos para %s (%s)", town_name, edition_date)
    return None


def _aemet_get(url: str, headers: dict) -> dict | None:
    """Llama al endpoint meta de AEMET (devuelve la URL de datos)."""
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _aemet_data(datos_url: str) -> list | None:
    """Descarga el JSON de datos desde la URL pre-firmada de AEMET."""
    resp = requests.get(datos_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_horaria(dia: dict, hour: str) -> dict:
    """
    Extrae temperatura, viento, lluvia y estado del cielo para la hora indicada.
    AEMET horaria usa periodos de 2 dígitos para temperatura/viento ('17')
    y periodos de 4 dígitos para rangos en precipitación/estadoCielo ('1718').
    Se busca por coincidencia exacta primero, luego por rango que contenga la hora.
    """
    result = {
        "temperatura": None,
        "viento_dir": None,
        "viento_vel": None,
        "lluvia": None,
        "estado_cielo": None,
    }

    # Temperatura — periodo hora exacta ("17")
    for item in dia.get("temperatura", []):
        if item.get("periodo") == hour:
            result["temperatura"] = _to_num(item.get("value"))
            break

    # Viento — puede ser "vientoAndRachaMax" (horaria) o "viento" (diaria)
    # El periodo en horaria es la hora como string de 2 dígitos
    viento_list = dia.get("vientoAndRachaMax", []) or dia.get("viento", [])
    for item in viento_list:
        periodo = item.get("periodo", "")
        if periodo == hour or _period_contains_hour(periodo, int(hour)):
            dir_val = item.get("direccion", [])
            vel_val = item.get("velocidad", [])
            result["viento_dir"] = dir_val[0] if isinstance(dir_val, list) else dir_val
            result["viento_vel"] = _to_num(vel_val[0] if isinstance(vel_val, list) else vel_val)
            break

    # Precipitación — puede ser rango de 4 dígitos ("1718") o exacto ("17")
    for item in dia.get("precipitacion", []):
        periodo = item.get("periodo", "")
        if periodo == hour or _period_contains_hour(periodo, int(hour)):
            result["lluvia"] = _to_num(item.get("value"))
            break

    # Estado cielo
    for item in dia.get("estadoCielo", []):
        periodo = item.get("periodo", "")
        if periodo == hour or _period_contains_hour(periodo, int(hour)):
            result["estado_cielo"] = item.get("descripcion") or item.get("value")
            break

    return result


def _parse_diaria(dia: dict) -> dict:
    vientos = dia.get("viento", [])
    viento = vientos[0] if vientos else {}
    prob_prec = dia.get("probPrecipitacion", [{}])
    cielo = dia.get("estadoCielo", [{}])
    return {
        "temperatura": _to_num(dia.get("temperatura", {}).get("maxima")),
        "viento_dir": viento.get("direccion"),
        "viento_vel": _to_num(viento.get("velocidad")),
        "lluvia": _to_num((prob_prec[0] if prob_prec else {}).get("value")),
        "estado_cielo": (cielo[0] if cielo else {}).get("descripcion"),
    }


def _period_contains_hour(periodo: str, hour: int) -> bool:
    """Comprueba si un periodo AEMET de 4 dígitos ('1718') contiene la hora dada."""
    if len(periodo) == 4:
        try:
            start = int(periodo[:2])
            end = int(periodo[2:])
            return start <= hour < end
        except ValueError:
            pass
    return False


def _to_num(val):
    """Convierte a int/float si es posible, si no devuelve None."""
    if val is None or val == "":
        return None
    try:
        f = float(val)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None
