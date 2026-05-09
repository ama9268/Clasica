import gpxpy
from django.contrib.gis.geos import LineString
import math

def parse_gpx_file(gpx_file):
    """
    Lee un archivo GPX y extrae la geometría, distancia y perfil de elevación.
    """
    try:
        gpx = gpxpy.parse(gpx_file)
    except Exception as e:
        return None, None, None

    points = []
    elevation_profile = []
    total_distance = 0
    previous_point = None

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # Añadir punto a la geometría (Longitud, Latitud)
                points.append((point.longitude, point.latitude))
                
                # Calcular distancia acumulada
                if previous_point:
                    dist = point.distance_2d(previous_point)
                    total_distance += dist
                
                # Añadir al perfil de elevación (Distancia en km, Altitud en m)
                elevation_profile.append({
                    "dist": round(total_distance / 1000, 3),
                    "alt": round(point.elevation, 1) if point.elevation is not None else 0
                })
                previous_point = point

    if not points:
        return None, None, None

    # Crear LineString para GeoDjango
    geometry = LineString(points)
    distance_km = round(total_distance / 1000, 2)

    return geometry, distance_km, elevation_profile
