import os
import requests
import logging
from django.core.cache import cache
from datetime import date

logger = logging.getLogger(__name__)

# Poblaciones de la ruta con sus códigos INE
ROUTE_TOWNS = {
    "Llerena": "06074",
    "Berlanga": "06019",
    "Valverde de Llerena": "06144",
    "Fuente del Arco": "06053",
    "Casas de Reina": "06034"
}

def get_weather_forecast_for_edition(edition_date: date):
    """
    Obtiene la previsión meteorológica promediada para los puntos clave de la ruta.
    """
    # Intentamos obtener de la configuración de Django o del entorno
    from django.conf import settings
    api_key = getattr(settings, "AEMET_API_KEY", os.environ.get("AEMET_API_KEY", "")).strip()
    
    if not api_key:
        logger.error("AEMET_API_KEY no encontrada.")
        return None

    cache_key = f"aemet_multi_forecast_{edition_date.isoformat()}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    all_forecasts = []
    logger.info(f"Consultando meteorología para {edition_date} en {len(ROUTE_TOWNS)} poblaciones...")
    
    for town_name, ine_code in ROUTE_TOWNS.items():
        f = _get_single_town_forecast(ine_code, edition_date, api_key)
        if f:
            all_forecasts.append(f)
        else:
            logger.warning(f"No se pudo obtener previsión para {town_name}")

    if not all_forecasts:
        # Re-intento final solo con Llerena si todo lo demás falla
        logger.info("Fallo multi-población, reintentando solo Llerena...")
        f_llerena = _get_single_town_forecast("06074", edition_date, api_key)
        if f_llerena:
            cache.set(cache_key, f_llerena, timeout=3600)
            return f_llerena
        return None

    # Promediamos los resultados para una representación global
    result = _average_forecasts(all_forecasts)
    cache.set(cache_key, result, timeout=3600)
    return result

def _get_single_town_forecast(ine_code, edition_date, api_key):
    headers = {"api_key": api_key, "Accept": "application/json"}
    try:
        # 1. Horaria
        url = f"https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/horaria/{ine_code}"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200 and res.json().get("estado") == 200:
            datos_url = res.json().get("datos")
            weather_data = requests.get(datos_url, timeout=5).json()
            if weather_data:
                dias = weather_data[0].get("prediccion", {}).get("dia", [])
                for dia in dias:
                    if dia.get("fecha", "").startswith(edition_date.isoformat()):
                        return _parse_horaria(dia, "17")

        # 2. Diaria (Fallback)
        url_d = f"https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/diaria/{ine_code}"
        res = requests.get(url_d, headers=headers, timeout=5)
        if res.status_code == 200 and res.json().get("estado") == 200:
            datos_url = res.json().get("datos")
            weather_data = requests.get(datos_url, timeout=5).json()
            if weather_data:
                prediccion = weather_data[0].get("prediccion", {})
                for dia in prediccion.get("dia", []):
                    if dia.get("fecha", "").startswith(edition_date.isoformat()):
                        return _parse_diaria(dia)
    except Exception:
        pass
    return None

def _average_forecasts(forecasts):
    # Simplificación: tomamos el primer estado de cielo y promediamos valores numéricos
    valid_temps = [f["temperatura"] for f in forecasts if f["temperatura"] is not None]
    valid_winds = [f["viento_vel"] for f in forecasts if f["viento_vel"] is not None]
    
    return {
        "temperatura": round(sum(valid_temps) / len(valid_temps)) if valid_temps else None,
        "viento_dir": forecasts[0]["viento_dir"], # Tomamos dirección del primer punto (Llerena)
        "viento_vel": round(sum(valid_winds) / len(valid_winds)) if valid_winds else 0,
        "lluvia": forecasts[0]["lluvia"],
        "estado_cielo": forecasts[0]["estado_cielo"],
        "is_multi": True
    }


def _parse_horaria(dia, hour):
    forecast = {"temperatura": None, "viento_dir": None, "viento_vel": None, "lluvia": None, "estado_cielo": None}
    for temp in dia.get("temperatura", []):
        if temp.get("periodo") == hour:
            forecast["temperatura"] = temp.get("value")
            break
    viento_list = dia.get("vientoAndRachaMax", []) or dia.get("viento", [])
    for viento in viento_list:
        if viento.get("periodo") == hour:
            forecast["viento_dir"] = viento.get("direccion")
            forecast["viento_vel"] = viento.get("velocidad")
            break
    for prec in dia.get("precipitacion", []):
        if prec.get("periodo") == hour:
            forecast["lluvia"] = prec.get("value")
            break
    for cielo in dia.get("estadoCielo", []):
        if cielo.get("periodo") == hour:
            forecast["estado_cielo"] = cielo.get("descripcion")
            break
    return forecast

def _parse_diaria(dia):
    # En diaria usamos valores máximos/medios
    vientos = dia.get("viento", [])
    viento = vientos[0] if vientos else {}
    return {
        "temperatura": dia.get("temperatura", {}).get("maxima"),
        "viento_dir": viento.get("direccion"),
        "viento_vel": viento.get("velocidad"),
        "lluvia": dia.get("probPrecipitacion", [{}])[0].get("value"), # Probabilidad en diaria
        "estado_cielo": dia.get("estadoCielo", [{}])[0].get("descripcion"),
    }
