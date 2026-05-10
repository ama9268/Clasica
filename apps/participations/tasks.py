import logging

logger = logging.getLogger(__name__)


def validate_track(
    edition_geometry,
    user_geometry,
    threshold_m: float | None = None,
    min_score: float | None = None,
) -> tuple[float, bool]:
    """
    Valida el track GPS del participante contra la ruta oficial de la edición.
    Usa PostGIS nativo (ST_DWithin + ST_DumpPoints) para máximo rendimiento.
    Retorna (score, is_valid).
    """
    from django.conf import settings
    from django.db import connection

    threshold_m = threshold_m or settings.GPX_MATCH_THRESHOLD_METERS
    min_score = min_score or settings.GPX_MATCH_MIN_SCORE

    if not edition_geometry or not user_geometry:
        return 0.0, False

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH official_points AS (
                SELECT (ST_DumpPoints(ST_Transform(ST_GeomFromEWKB(%s::bytea), 3857))).geom AS pt
            )
            SELECT
                COUNT(*) AS total_pts,
                SUM(CASE WHEN ST_DWithin(pt, ST_Transform(ST_GeomFromEWKB(%s::bytea), 3857), %s)
                    THEN 1 ELSE 0 END) AS matched_pts
            FROM official_points;
            """,
            [edition_geometry.ewkb, user_geometry.ewkb, threshold_m],
        )
        row = cursor.fetchone()

    total_pts = row[0] or 0
    matched_pts = row[1] or 0

    if total_pts == 0:
        return 0.0, False

    score = matched_pts / total_pts
    return round(score, 4), score >= min_score
