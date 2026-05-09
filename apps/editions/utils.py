import logging
import gpxpy
from django.contrib.gis.geos import LineString

logger = logging.getLogger(__name__)

def parse_gpx_to_geometry_and_elevation(gpx_file) -> tuple[LineString | None, float | None, list | None]:
    """
    Parses a GPX file and returns the LineString geometry, distance in km, 
    and the elevation profile as a list of [distance_km, elevation_m].
    """
    try:
        # Re-read file from the beginning
        gpx_file.seek(0)
        gpx = gpxpy.parse(gpx_file)
    except Exception:
        logger.exception("Error parsing GPX file")
        return None, None, None

    coords = []
    elevation_profile = []
    distance_from_start = 0.0

    for track in gpx.tracks:
        for segment in track.segments:
            prev_point = None
            for point in segment.points:
                coords.append((point.longitude, point.latitude))
                if prev_point:
                    distance_from_start += point.distance_2d(prev_point)
                
                # Use GPX elevation or 0.0 as default if not available
                ele = point.elevation if point.elevation is not None else 0.0
                dist_km = round(distance_from_start / 1000, 2)
                elevation_profile.append([dist_km, round(ele, 1)])
                
                prev_point = point

    geom = LineString(coords) if coords else None
    distance_km = round(gpx.length_2d() / 1000, 2) if coords else None
    ele_profile = elevation_profile if elevation_profile else None

    return geom, distance_km, ele_profile
