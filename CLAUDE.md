# Clasica — Prueba Ciclista Semanal

## Visión General
Gestión de una prueba ciclista semanal. Los participantes se registran desde la web o la app móvil. **La app móvil registra el track GPS durante la prueba y lo envía al backend al finalizar.** El backend valida el recorrido contra la ruta oficial con PostGIS y genera la clasificación automáticamente.

## Stack Tecnológico
- **Backend:** Django 6 + DRF + SimpleJWT
- **Base de datos:** PostgreSQL + PostGIS
- **Geolocalización:** GeoDjango (`LineStringField`, `ST_DWithin`, `ST_DumpPoints`)
- **Frontend / Mapas:** Tailwind CSS, Alpine.js, Leaflet.js, Chart.js
- **Tiempo real:** Django Channels (Daphne ASGI) + Redis (tracking en vivo por WebSocket)
- **App Móvil:** React Native (Expo) en `mobile/`
- **Meteorología:** AEMET API

> Strava eliminado. El track GPS lo aporta directamente la app móvil.

## Estructura de Apps

| App | Propósito |
|-----|-----------|
| `accounts/` | Auth y perfiles de usuario |
| `editions/` | Ediciones, variantes de ruta, galería de medios |
| `participations/` | Inscripciones y actividades GPS enviadas desde la app |
| `classifications/` | Tiempos y posiciones por categoría de edad |
| `tracking/` | WebSocket para seguimiento en vivo durante la prueba |
| `dashboard/` | Panel web del organizador (staff only) |
| `api/` | Endpoints DRF + JWT para la app móvil |

## Modelos — Resumen

### `accounts.UserProfile` (hereda `AbstractUser`)
```python
full_name, birth_date, photo, club
```

### `editions.RouteVariant`
Ruta reutilizable entre ediciones.
```python
name, description, route_gpx
route_geometry: LineStringField(srid=4326)
route_distance_km, elevation_profile (JSONField)
@property route_geojson: str | None
```

### `editions.Edition`
```python
date (unique), name, start_time (default 16:30)
route_variant: FK(RouteVariant, nullable)
route_gpx, route_geometry: LineStringField(srid=4326, nullable)
route_distance_km, elevation_profile (JSONField)
status: ('open' | 'closed' | 'results_published')
@property is_registration_open, results_published, is_live, has_started
@property route_geojson, get_elevation_profile, get_route_distance, total_elevation_gain
```

### `editions.EditionMedia`
```python
edition: FK(Edition, related_name='media')
media_type: ('photo' | 'video')
photo: ImageField(upload_to='editions/media/')
video_url: URLField
caption, order
@property embed_url   # convierte YouTube/Vimeo a embebible
```

### `participations.Participation`
```python
user: FK(UserProfile), edition: FK(Edition)
unique_together: (user, edition)
```

### `participations.Activity`
Actividad GPS enviada por la app móvil al terminar la prueba.
```python
participation: OneToOne(Participation, related_name='activity')
elapsed_time_seconds: PositiveIntegerField
track_geometry: LineStringField(srid=4326)
is_valid: bool, validation_score: float
recorded_at: DateTimeField
@property elapsed_formatted: str   # HH:MM:SS
@property track_geojson: dict | None
```

### `classifications.Classification`
```python
participation: OneToOne(Participation)
time_seconds, category: ('open' | 'M40' | 'M50' | 'M60')
position_overall, position_category
@property time_formatted: str
```
> Categorías por edad en la fecha de la edición: Open (<40), M40 (40–49), M50 (50–59), M60 (60+).

## Flujo principal — App Móvil → Backend

1. Usuario se registra/login en la app (`POST /api/v1/auth/register/` o `/auth/login/`).
2. Se inscribe en la edición (`POST /api/v1/editions/<pk>/register/`).
3. Durante la prueba, la app registra posiciones GPS y las emite por WebSocket (`ws/tracking/<edition_id>/`) para el mapa en vivo.
4. Al finalizar, la app envía el track completo (`POST /api/v1/editions/<pk>/activity/`):
   ```json
   { "track_geojson": {"type":"LineString","coordinates":[[lon,lat],...]}, "elapsed_time_seconds": 3600 }
   ```
5. El backend valida con `validate_track()` (PostGIS) y responde:
   ```json
   { "is_valid": true, "validation_score": 0.94, "elapsed_time_seconds": 3600, "elapsed_formatted": "01:00:00" }
   ```
6. El organizador publica resultados desde el dashboard (`POST /dashboard/editions/<pk>/publish/`).

## Validación Geoespacial Nativa
`participations/tasks.py::validate_track(edition_geometry, user_geometry, threshold_m=100, min_score=0.80)`:
- `ST_Transform` a SRID 3857 (metros).
- `ST_DumpPoints` densifica la ruta oficial.
- `ST_DWithin` comprueba cada punto del track del participante.
- `score = matched_pts / total_pts`. `is_valid` si `score >= 0.80`.

**Nunca calcular distancias con Haversine en Python. Siempre delegar a PostGIS.**

## Tracking en Tiempo Real
- WebSocket en `ws/tracking/<edition_id>/` → `TrackingConsumer`.
- Posiciones **efímeras**: Redis Channel Layer, sin persistencia en BD.
- Grupo Redis: `f"tracking_{edition_id}"`.
- Mensaje: `{type, user_id, username, lat, lng, speed}`.

## AEMET — Meteorología
`apps/editions/services/aemet.py::get_weather_forecast_for_edition(edition_date)`:
- Consulta 5 poblaciones de la zona por código INE.
- Prioriza previsión horaria (17:00), fallback a diaria.
- Cache 1 hora.
- Retorna: `{temperatura, viento_dir, viento_vel, lluvia, estado_cielo}`.

## GPX Parsing
- `apps/editions/utils.py::parse_gpx_to_geometry_and_elevation(gpx_file)` → `(LineString, km, list)`.
- `apps/editions/services/gpx_parser.py::parse_gpx_file(gpx_file)` → perfil `[{"dist": km, "alt": m}]`.
- Coordenadas siempre como `(lon, lat)` para SRID 4326.

## Context Processor
`clasica_project/context_processors.py::open_edition(request)`:
- `open_edition`: edición con `status='open'` más próxima, o `None`.
- `user_registered`: `bool` si el usuario autenticado está inscrito.
- Controla el botón **ÚNETE** en la navbar.

## URLs — Mapa completo

### API REST (`/api/v1/`)
| Método | URL | Descripción |
|--------|-----|-------------|
| POST | `auth/register/` | Registro |
| POST | `auth/login/` | JWT login |
| POST | `auth/token/refresh/` | Renovar token |
| GET/PATCH | `auth/me/` | Perfil propio |
| GET | `editions/` | Lista ediciones |
| GET | `editions/<pk>/` | Detalle + ruta GeoJSON |
| POST | `editions/<pk>/register/` | Inscribirse |
| **POST** | **`editions/<pk>/activity/`** | **Subir track GPS** |
| GET | `classifications/general/` | Clasificación general |
| GET | `stats/user/<pk>/` | Stats de un usuario |

### WebSocket
```
ws/tracking/<edition_id>/   →   TrackingConsumer
```

### Dashboard (staff)
| URL | Acción |
|-----|--------|
| `/dashboard/editions/<pk>/publish/` | Publicar resultados |
| `/dashboard/editions/<pk>/media/add/` | Añadir foto/vídeo |
| `/dashboard/media/<pk>/delete/` | Borrar media |
| `/dashboard/activities/<pk>/validate/` | Toggle validación manual |
| `/dashboard/variants/new/` | Crear variante de ruta |

## Publicación de Resultados
`dashboard/views.py::_recalculate_positions(edition)`:
1. Filtra `Activity` válidas de la edición, ordenadas por `elapsed_time_seconds`.
2. Calcula categoría con `get_category(birth_date, edition_date)`.
3. Crea/actualiza `Classification` con posición general y por categoría.
4. `edition.status = 'results_published'`.

## App Móvil (`mobile/`)
Expo Router + TypeScript. Ver [mobile/README.md](mobile/README.md).

| Pantalla | Ruta |
|----------|------|
| Login / Registro | `(auth)/login`, `(auth)/register` |
| Lista ediciones | `(tabs)/index` |
| Clasificación | `(tabs)/clasificacion` |
| Perfil + historial | `(tabs)/perfil` |
| Detalle edición + mapa | `editions/[id]` |
| Tracking en vivo | `live/[id]` |

La subida del track se hace con `uploadActivity()` de `src/api/editions.ts`.

## Reglas de Desarrollo

1. **PostGIS nativo:** operaciones espaciales siempre en la BD, nunca Haversine en Python.
2. **Seguridad:** filtrar querysets por `request.user`; nunca aceptar `user` como input de serializer.
3. **Geometría:** `route_geojson` y `track_geojson` son `@property` calculadas, no columnas en BD.
4. **Acceso:** todas las vistas de ediciones y clasificaciones requieren `LoginRequired`.
5. **Media:** fotos en `editions/media/`; vídeos como URL. `embed_url` convierte a embebible.
6. **Entorno Windows:** definir `GDAL_LIBRARY_PATH` y `GEOS_LIBRARY_PATH` en `settings/base.py`.
7. **`related_name` clave:** `participation.activity` (no `strava_activity`).

## Despliegue (Dokploy)
- `docker-compose.yml`: `web` (Daphne ASGI, puerto 8000) + `worker` (Celery, reservado para futuras tareas).
- `entrypoint.sh`: `web` ejecuta `migrate` + `collectstatic` + `daphne`; `worker` ejecuta `celery`.
- BD y Redis son contenedores externos en `dokploy-network`.
- La BD **debe** usar imagen `postgis/postgis`.
- Volumen `media_data` compartido entre `web` y `worker`.
