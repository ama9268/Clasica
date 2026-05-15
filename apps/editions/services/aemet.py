import os
import requests
import logging
from django.core.cache import cache
from datetime import date

logger = logging.getLogger(__name__)

LLERENA_INE = "06074"
AEMET_BASE  = "https://opendata.aemet.es/opendata/api"
TIMEOUT     = 8


def get_weather_forecast_for_edition(edition_date: date, start_hour: int = 16):
    from django.conf import settings
    api_key = getattr(settings, "AEMET_API_KEY", os.environ.get("AEMET_API_KEY", "")).strip()
    if not api_key:
        logger.error("AEMET_API_KEY no configurada.")
        return None

    cache_key = f"aemet_{edition_date.isoformat()}_{start_hour}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    headers = {"api_key": api_key, "Accept": "application/json"}
    hour = f"{start_hour:02d}"

    result = _fetch_horaria(edition_date, hour, headers) or _fetch_diaria(edition_date, headers)

    if result:
        cache.set(cache_key, result, timeout=3600)
    return result


def _fetch_horaria(edition_date: date, hour: str, headers: dict):
    try:
        meta = requests.get(
            f"{AEMET_BASE}/prediccion/especifica/municipio/horaria/{LLERENA_INE}",
            headers=headers, timeout=TIMEOUT,
        )
        meta.raise_for_status()
        datos_url = meta.json().get("datos")
        if not datos_url:
            return None
        data = requests.get(datos_url, timeout=TIMEOUT)
        data.raise_for_status()
        dias = data.json()[0].get("prediccion", {}).get("dia", [])
        for dia in dias:
            if dia.get("fecha", "").startswith(edition_date.isoformat()):
                parsed = _parse_horaria(dia, hour)
                if parsed.get("temperatura") is not None:
                    logger.info("AEMET horaria OK hora=%s", hour)
                    return parsed
    except Exception as exc:
        logger.warning("AEMET horaria falló: %s", exc)
    return None


def _fetch_diaria(edition_date: date, headers: dict):
    try:
        meta = requests.get(
            f"{AEMET_BASE}/prediccion/especifica/municipio/diaria/{LLERENA_INE}",
            headers=headers, timeout=TIMEOUT,
        )
        meta.raise_for_status()
        datos_url = meta.json().get("datos")
        if not datos_url:
            return None
        data = requests.get(datos_url, timeout=TIMEOUT)
        data.raise_for_status()
        dias = data.json()[0].get("prediccion", {}).get("dia", [])
        for dia in dias:
            if dia.get("fecha", "").startswith(edition_date.isoformat()):
                parsed = _parse_diaria(dia)
                if parsed.get("temperatura") is not None:
                    logger.info("AEMET diaria OK (fallback)")
                    return parsed
    except Exception as exc:
        logger.warning("AEMET diaria falló: %s", exc)
    return None


def _parse_horaria(dia: dict, hour: str) -> dict:
    result = {"temperatura": None, "viento_dir": None, "viento_vel": None,
              "lluvia": None, "estado_cielo": None}
    h = int(hour)

    for item in dia.get("temperatura", []):
        if item.get("periodo") == hour:
            result["temperatura"] = _num(item.get("value"))
            break

    for item in dia.get("vientoAndRachaMax", []) or dia.get("viento", []):
        p = item.get("periodo", "")
        if p == hour or _in_range(p, h):
            d = item.get("direccion", [])
            v = item.get("velocidad", [])
            result["viento_dir"] = d[0] if isinstance(d, list) else d
            result["viento_vel"] = _num(v[0] if isinstance(v, list) else v)
            break

    for item in dia.get("precipitacion", []):
        p = item.get("periodo", "")
        if p == hour or _in_range(p, h):
            result["lluvia"] = _num(item.get("value"))
            break

    for item in dia.get("estadoCielo", []):
        p = item.get("periodo", "")
        if p == hour or _in_range(p, h):
            result["estado_cielo"] = item.get("descripcion") or item.get("value")
            break

    return result


def _parse_diaria(dia: dict) -> dict:
    viento = (dia.get("viento") or [{}])[0]
    prob   = (dia.get("probPrecipitacion") or [{}])[0]
    cielo  = (dia.get("estadoCielo") or [{}])[0]
    return {
        "temperatura":  _num(dia.get("temperatura", {}).get("maxima")),
        "viento_dir":   viento.get("direccion"),
        "viento_vel":   _num(viento.get("velocidad")),
        "lluvia":       _num(prob.get("value")),
        "estado_cielo": cielo.get("descripcion"),
    }


def _in_range(periodo: str, hour: int) -> bool:
    if len(periodo) == 4:
        try:
            return int(periodo[:2]) <= hour < int(periodo[2:])
        except ValueError:
            pass
    return False


def _num(val):
    if val is None or val == "":
        return None
    try:
        f = float(val)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None
