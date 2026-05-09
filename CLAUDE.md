# Clasica — Prueba Ciclista Semanal

## Visión General
Gestión de una prueba ciclista semanal. Los participantes se registran y Strava notifica automáticamente las actividades coincidentes con la ruta oficial vía webhook. Incluye tracking en tiempo real (móvil y web), clasificaciones por categoría de edad y galería de medios por edición.

## Stack Tecnológico
- **Backend:** Django 6 + DRF + SimpleJWT
- **Base de datos:** PostgreSQL + PostGIS (vía Dokploy en VPS)
- **Geolocalización:** GeoDjango (`LineStringField`, `ST_DWithin`, `ST_DumpPoints`)
- **Frontend / Mapas:** Tailwind CSS, Alpine.js, Leaflet.js, Chart.js
- **Tiempo real / Tareas:** Django Channels (Daphne ASGI) + Redis + Celery
- **App Móvil:** React Native (Expo)
- **Meteorología:** AEMET API (España)

## Estructura de Apps

| App | Propósito |
|-----|-----------|
| `accounts/` | Auth, perfiles y Strava OAuth |
| `editions/` | Ediciones, variantes de ruta, galería de medios |
| `participations/` | Inscripciones, webhook Strava, importación automática |
| `classifications/` | Tiempos y posiciones por categoría de edad |
| `tracking/` | WebSocket para seguimiento en vivo |
| `dashboard/` | Panel web del organizador (staff only) |
| `api/` | Endpoints DRF + JWT para la app móvil |

## Modelos — Resumen

### `accounts.UserProfile` (hereda `AbstractUser`)
```python
full_name, birth_date, photo, club
strava_athlete_id (unique), strava_access_token, strava_refresh_token, strava_token_expires_at
@property strava_connected: bool
@property strava_token_expired: bool
```

### `editions.RouteVariant`
Ruta reutilizable entre ediciones. Contiene GPX propio y perfil de elevación.
```python
name, description, route_gpx
route_geometry: LineStringField(srid=4326)
route_distance_km, elevation_profile (JSONField)
@property route_geojson: str | None
```

### `editions.Edition`
```python
date (unique), name, start_time (default 16:30)
route_variant: FK(RouteVariant, nullable)   # ruta reutilizable
route_gpx, route_geometry: LineStringField(srid=4326, nullable)  # ruta propia opcional
route_distance_km, elevation_profile (JSONField)
status: ('open' | 'closed' | 'results_published')
@property is_registration_open, results_published, is_live, has_started
@property route_geojson, get_elevation_profile, get_route_distance
@property total_elevation_gain: int  # suma altimetría positiva
```

### `editions.EditionMedia`
```python
edition: FK(Edition, related_name='media')
media_type: ('photo' | 'video')
photo: ImageField(upload_to='editions/media/')
video_url: URLField        # YouTube o Vimeo
caption, order
@property embed_url: str   # convierte YT/Vimeo a URL embebible
```

### `participations.Participation`
```python
user: FK(UserProfile), edition: FK(Edition)
unique_together: (user, edition)
```

### `participations.StravaActivity`
```python
participation: OneToOne(Participation)
strava_activity_id (unique), elapsed_time_seconds
track_geometry: LineStringField(srid=4326)   # nunca track_geojson JSON
is_valid: bool, validation_score: float
@property elapsed_formatted: str  # HH:MM:SS
@property track_geojson: dict | None
```

### `classifications.Classification`
```python
participation: OneToOne(Participation)
time_seconds, category: ('open' | 'M40' | 'M50' | 'M60')
position_overall, position_category
@property time_formatted: str  # HH:MM:SS
```
> Categorías por edad en la fecha de la edición: Open (<40), M40 (40-49), M50 (50-59), M60 (60+).

## Flujo Strava

1. **OAuth** (`/accounts/strava/connect/`) → redirige a Strava. Callback guarda tokens.
2. **Webhook** (`/webhooks/strava/`) → Strava POST con `activity_id`. Se valida firma HMAC y se encola Celery task inmediatamente.
3. **Auto-importación** (`participations/tasks.py::process_strava_activity`):
   - Refresca token si expirado.
   - Descarga detalles + GPS streams de Strava API.
   - Sólo procesa `type=Ride` o `type=VirtualRide`.
   - Crea `LineString track_geometry` SRID 4326.
   - Valida con `validate_track()` (nativo PostGIS).
   - Crea/actualiza `StravaActivity`.

## Validación Geoespacial Nativa
En `participations/tasks.py::validate_track(edition_geometry, user_geometry, threshold_m=100, min_score=0.80)`:
- `ST_Transform` a SRID 3857 (metros).
- `ST_DumpPoints` densifica la ruta oficial.
- `ST_DWithin` comprueba cada punto del track.
- `score = matched_pts / total_pts`. `is_valid` si `score >= 0.80`.

**Nunca calcular distancias con Haversine en Python. Siempre delegar a PostGIS.**

## Tracking en Tiempo Real
- WebSocket en `ws/tracking/<edition_id>/` → `TrackingConsumer`.
- Posiciones **efímeras**: Redis Channel Layer, sin persistencia en BD.
- Grupo Redis: `f"tracking_{edition_id}"`.
- Mensaje emitido: `{type, user_id, username, lat, lng, speed}`.
- Leaflet.js (web) y React Native Maps (móvil) actualizan marcadores.

## AEMET — Meteorología
`apps/editions/services/aemet.py::get_weather_forecast_for_edition(edition_date)` → `dict | None`:
- Consulta 5 poblaciones de la zona (Llerena, Berlanga, etc.) por código INE.
- Prioriza previsión horaria (hora 17:00), fallback a diaria.
- Cache 1 hora.
- Retorna: `{temperatura, viento_dir, viento_vel, lluvia, estado_cielo}`.

## GPX Parsing
- `apps/editions/utils.py::parse_gpx_to_geometry_and_elevation(gpx_file)` → `(LineString | None, float | None, list | None)`.
- `apps/editions/services/gpx_parser.py::parse_gpx_file(gpx_file)` → perfil como `[{"dist": km, "alt": m}, ...]`.
- Ambas usan `gpxpy`. Coordenadas como `(lon, lat)` para SRID 4326.

## Context Processor
`clasica_project/context_processors.py::open_edition(request)` inyecta en todos los templates:
- `open_edition`: edición con `status='open'` más próxima, o `None`.
- `user_registered`: `bool` si el usuario ya está inscrito en esa edición.
- Controla la visibilidad del botón **ÚNETE** en la navbar.

## URLs — Mapa completo

### Pública
| URL | Vista |
|-----|-------|
| `/` | `HomeView` |
| `/editions/` | `EditionListView` (LoginRequired) |
| `/editions/<pk>/` | `EditionDetailView` (LoginRequired) |
| `/editions/<pk>/register/` | `edition_register` (LoginRequired) |
| `/clasificacion/` | `GeneralClassificationView` (LoginRequired) |
| `/perfil/<pk>/` | `PublicProfileView` (LoginRequired) |
| `/live/<edition_id>/` | `LiveTrackingView` (LoginRequired) |

### Accounts
| URL | Vista |
|-----|-------|
| `/accounts/login/` | `LoginView` |
| `/accounts/logout/` | `LogoutView` (POST) |
| `/accounts/register/` | `RegisterView` |
| `/accounts/profile/` | `ProfileView` |
| `/accounts/strava/connect/` | `strava_connect` |
| `/accounts/strava/callback/` | `strava_callback` |
| `/accounts/strava/disconnect/` | `strava_disconnect` (POST) |

### Dashboard (staff only)
| URL | Vista |
|-----|-------|
| `/dashboard/` | `DashboardHomeView` |
| `/dashboard/editions/` | `EditionListView` |
| `/dashboard/editions/new/` | `EditionCreateView` |
| `/dashboard/editions/<pk>/` | `EditionDetailView` |
| `/dashboard/editions/<pk>/edit/` | `EditionUpdateView` |
| `/dashboard/editions/<pk>/delete/` | `EditionDeleteView` |
| `/dashboard/editions/<pk>/publish/` | `publish_results` (POST) |
| `/dashboard/editions/<pk>/media/add/` | `media_add` (POST) |
| `/dashboard/media/<pk>/delete/` | `media_delete` (POST) |
| `/dashboard/activities/<pk>/validate/` | `override_validation` (POST) |
| `/dashboard/variants/` | `RouteVariantListView` |
| `/dashboard/variants/new/` | `RouteVariantCreateView` |

### API REST (`/api/v1/`)
| Método | URL | Vista |
|--------|-----|-------|
| POST | `auth/register/` | `RegisterAPIView` |
| POST | `auth/login/` | `TokenObtainPairView` (JWT) |
| POST | `auth/token/refresh/` | `TokenRefreshView` |
| GET/PATCH | `auth/me/` | `MeAPIView` |
| GET | `editions/` | `EditionListAPIView` |
| GET | `editions/<pk>/` | `EditionDetailAPIView` |
| POST | `editions/<pk>/register/` | `EditionRegisterAPIView` |
| GET | `classifications/general/` | `GeneralClassificationAPIView` |
| GET | `stats/user/<pk>/` | `UserStatsAPIView` |
| GET | `strava/connect/` | `StravaConnectAPIView` |
| POST | `strava/disconnect/` | `StravaDisconnectAPIView` |

### WebSocket
```
ws/tracking/<edition_id>/   →   TrackingConsumer
```

### Webhook
```
POST /webhooks/strava/   →   strava_webhook (valida HMAC, encola Celery)
```

## Publicación de Resultados (Admin)
`dashboard/views.py::publish_results` → `_recalculate_positions(edition)`:
1. Filtra `StravaActivity` válidas de la edición, ordenadas por `elapsed_time_seconds`.
2. Para cada actividad, calcula categoría con `get_category(birth_date, edition_date)`.
3. Crea/actualiza `Classification` con `position_overall` y `position_category`.
4. Cambia `edition.status = 'results_published'`.

## Reglas de Desarrollo

1. **GeoDjango nativo:** operaciones espaciales siempre en la BD (PostGIS), nunca bucles Haversine en Python.
2. **Seguridad en vistas:** filtrar siempre querysets por `request.user`; jamás aceptar `user` como input de serializer.
3. **Validación webhooks:** `hmac.compare_digest` en tiempo constante con `STRAVA_CLIENT_SECRET`.
4. **Celery:** llamadas a Strava API y parseo de GPX grandes deben ir a `tasks.py`.
5. **Entorno Windows:** definir `GDAL_LIBRARY_PATH` y `GEOS_LIBRARY_PATH` en `settings/base.py` si `os.name == 'nt'`.
6. **Geometría:** los campos `route_geojson` y `track_geojson` son `@property` calculadas — no columnas en BD.
7. **Acceso a ediciones:** todas las vistas públicas de ediciones y clasificaciones requieren `LoginRequired`.
8. **Media:** fotos se guardan en `editions/media/`; vídeos como URL (YouTube/Vimeo). `embed_url` convierte a embebible.

## Despliegue (Dokploy)
- `docker-compose.yml`: servicio `web` (Daphne ASGI, puerto 8000) + `worker` (Celery).
- `entrypoint.sh`: si `SERVICE=worker` ejecuta `celery`, si `web` ejecuta `migrate` + `collectstatic` + `daphne`.
- Base de datos y Redis son contenedores externos en `dokploy-network`.
- La BD **debe** usar imagen `postgis/postgis` para la extensión PostGIS.
- Volumen `media_data` compartido entre `web` y `worker` para archivos subidos.
