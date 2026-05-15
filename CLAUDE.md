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
- **Tareas asíncronas:** Celery + Beat (cierre automático de ediciones)

> Strava eliminado. El track GPS lo aporta directamente la app móvil.

## Estructura de Apps

| App | Propósito |
|-----|-----------|
| `accounts/` | Auth y perfiles de usuario |
| `editions/` | Ediciones, variantes de ruta, galería de medios, tarea Celery |
| `participations/` | Inscripciones y actividades GPS enviadas desde la app |
| `classifications/` | Tiempos y posiciones por categoría de edad |
| `tracking/` | WebSocket para seguimiento en vivo durante la prueba |
| `dashboard/` | Panel web del organizador (staff only) |
| `api/` | Endpoints DRF + JWT para la app móvil |

## Modelos — Resumen

### `accounts.UserProfile` (hereda `AbstractUser`)
```python
full_name, birth_date, photo, club
# Strava OAuth (campos opcionales)
strava_athlete_id: BigIntegerField(nullable, unique)
strava_access_token, strava_refresh_token: CharField
strava_token_expires_at: DateTimeField(nullable)
@property strava_connected: bool
save()   # optimiza photo → WebP antes de persistir
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
@property route_geom: LineString | None   # propia si existe, si no la del route_variant
```

### `editions.EditionMedia`
```python
edition: FK(Edition, related_name='media')
media_type: ('photo' | 'video')
photo: ImageField(upload_to='editions/media/')
video_url: URLField
caption, order
@property embed_url   # convierte YouTube/Vimeo a embebible
save()               # optimiza photo → WebP antes de persistir
```

### `participations.Participation`
```python
user: FK(UserProfile), edition: FK(Edition)
registered_at: DateTimeField(auto_now_add=True)
unique_together: (user, edition)
```

### `participations.Activity`
Actividad GPS enviada por la app móvil al terminar la prueba.
**El track GPS se usa únicamente para la validación y no se persiste en BD.**
```python
participation: OneToOne(Participation, related_name='activity')
elapsed_time_seconds: PositiveIntegerField(nullable)
average_moving_speed: FloatField(nullable)   # km/h, solo puntos con velocidad > 0
is_valid: bool, validation_score: float(nullable)
recorded_at: DateTimeField
source: CharField(choices=['mobile','strava'], default='mobile')
strava_activity_id: BigIntegerField(nullable, unique)
@property elapsed_formatted: str   # HH:MM:SS
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
   {
     "track_geojson": {"type": "LineString", "coordinates": [[lon, lat], ...]},
     "elapsed_time_seconds": 3600,
     "average_moving_speed": 28.5
   }
   ```
5. El backend valida con `validate_track()` (PostGIS) — el track **no se guarda** — y responde:
   ```json
   {
     "is_valid": true,
     "validation_score": 0.94,
     "elapsed_time_seconds": 3600,
     "elapsed_formatted": "01:00:00",
     "average_moving_speed": 28.5
   }
   ```
6. Si la actividad es válida, se recalculan posiciones y la edición pasa a `results_published` automáticamente.
7. El organizador también puede publicar resultados manualmente desde el dashboard (`POST /dashboard/editions/<pk>/publish/`).

## Validación Geoespacial Nativa
`participations/tasks.py::validate_track(edition_geometry, user_geometry, threshold_m=None, min_score=None)`:
- Lee umbrales desde `settings.GPX_MATCH_THRESHOLD_METERS` y `settings.GPX_MATCH_MIN_SCORE`.
- `ST_Transform` a SRID 3857 (metros).
- `ST_DumpPoints` densifica la ruta oficial.
- `ST_DWithin` comprueba cada punto del track del participante contra la ruta oficial.
- `score = matched_pts / total_pts`. `is_valid` si `score >= min_score`.
- Retorna `tuple[float, bool]` → `(score, is_valid)`.

**Nunca calcular distancias con Haversine en Python. Siempre delegar a PostGIS.**

## Tareas Celery
`apps/editions/tasks.py::auto_close_expired_editions()`:
- Tarea periódica (Beat, cada 5 min). Se ejecuta a partir de las 21:30 sobre ediciones `open` del día.
- Si **no hay** finishers válidos → `status = closed`.
- Si **hay** finishers válidos → llama `recalculate_positions()` y pasa a `results_published`.
- El worker arranca con `celery -A clasica_project worker --beat -l info`.

## Comandos de Simulación (desarrollo/demo)

### `simulate_race`
Crea participantes simulados (prefijo `sim__`) con tracks GPS válidos e inválidos, valida y recalcula clasificación.
```bash
python manage.py simulate_race --edition <pk> --users 5 --invalid 2 --noise 0.0001 --clean
```
- `--clean`: elimina usuarios `sim__*` de la edición antes de generar nuevos.
- Tracks válidos: ruido ≈ 10 m. Inválidos: desviados ~5 km o recortados al 30 % de la ruta.

### `simulate_live`
Emite posiciones GPS de participantes `sim__*` en tiempo real vía Channel Layer (no persiste nada).
```bash
python manage.py simulate_live --edition <pk> --interval 2 --step 10 --spread 200
```
- `--step`: puntos que avanza cada tick. `--spread`: desfase inicial entre participantes.

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
- Solo se incluye en `EditionDetailSerializer` si la edición está `open`.

## GPX Parsing
- `apps/editions/utils.py::parse_gpx_to_geometry_and_elevation(gpx_file)` → `(LineString, km, list)`.
- `apps/editions/services/gpx_parser.py::parse_gpx_file(gpx_file)` → perfil `[{"dist": km, "alt": m}]`.
- Coordenadas siempre como `(lon, lat)` para SRID 4326.

## Integración Strava (opcional)

### Conexión OAuth
`apps/accounts/services/strava.py::StravaClient`:
- `get_auth_url(redirect_uri)` → URL de autorización Strava (`activity:read`).
- `exchange_code(code, redirect_uri)` → intercambia el code por tokens.
- `_ensure_fresh_token()` → refresca automáticamente si el token ha caducado.
- `get_activities_on_date(date)` → lista actividades Ride del atleta en esa fecha.
- `get_activity_linestring(activity_id)` → stream latlng → `GEOSLineString(srid=4326)`.
- `revoke_token()` → revoca en Strava y limpia campos del usuario.

Excepción: `StravaError`.

### Flujo móvil (automático con fallback)
1. Si `user.strava_connected`: `GET editions/<pk>/strava-activities/` → lista; usuario elige.
2. `POST editions/<pk>/activity/strava/` con `{strava_activity_id}` → descarga stream, valida PostGIS, guarda `Activity(source='strava')`.
3. Si falla o sin Strava: fallback a `POST editions/<pk>/activity/` con GPS propio.
4. Subida tardía permitida hasta `edition.date + STRAVA_ACTIVITY_UPLOAD_WINDOW_HOURS` (default 24 h).

### OAuth web
`GET /accounts/strava/callback/` → intercambia code y guarda tokens.
`POST /accounts/strava/disconnect/` → revoca y limpia.

### Endpoints Strava (`/api/v1/`)
| Método | URL | Descripción |
|--------|-----|-------------|
| GET | `auth/strava/auth-url/` | Devuelve URL de autorización |
| POST | `auth/strava/connect/` | Intercambia code, guarda tokens |
| POST | `auth/strava/disconnect/` | Revoca token y limpia campos |
| GET | `editions/<pk>/strava-activities/` | Actividades Ride del usuario en la fecha |
| POST | `editions/<pk>/activity/strava/` | Valida actividad Strava seleccionada |
| GET/POST | `strava/webhook/` | Recepción de Strava Push Subscriptions |

### Settings Strava
```python
STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET   # variables de entorno
STRAVA_REDIRECT_URI                       # URL callback web
STRAVA_ACTIVITY_UPLOAD_WINDOW_HOURS = 24  # ventana post-edición para subida tardía
```

### App Móvil
- `mobile/src/api/auth.ts`: `getStravaAuthUrl()`, `connectStrava()`, `disconnectStrava()`.
- `mobile/app/(tabs)/perfil.tsx`: bloque Strava con estado conectado/desconectado + flujo OAuth vía `expo-web-browser`.
- Deep link de callback: `clasica://strava-callback` (scheme `clasica` definido en `app.json`).

## Optimización de Imágenes
`clasica_project/image_utils.py::optimize_image(image_file, quality=82, max_dimension=1920)`:
- Convierte a **WebP** (calidad 82) y aplica rotación EXIF automáticamente.
- Redimensiona con LANCZOS si supera 1920 px en cualquier dimensión.
- Retorna `ContentFile` con extensión `.webp`. En caso de error devuelve el fichero original.
- Se invoca desde `UserProfile.save()` y `EditionMedia.save()` — no hay que llamarlo explícitamente.

## Context Processor
`clasica_project/context_processors.py::open_edition(request)`:
- `open_edition`: edición con `status='open'` más próxima, o `None`.
- `user_registered`: `bool` si el usuario autenticado está inscrito.
- Controla el botón **ÚNETE** en la navbar.

## URLs — Mapa completo

### Web pública
| URL | Vista |
|-----|-------|
| `/` | `HomeView` — pública, muestra `next_edition` y `last_editions` |
| `/editions/` | `EditionListView` — requiere login |
| `/editions/<pk>/` | `EditionDetailView` — requiere login |

### API REST (`/api/v1/`)
| Método | URL | Descripción |
|--------|-----|-------------|
| POST | `auth/register/` | Registro |
| POST | `auth/login/` | JWT login |
| POST | `auth/token/refresh/` | Renovar token |
| GET/PATCH | `auth/me/` | Perfil propio |
| GET | `editions/` | Lista ediciones |
| POST | `editions/` | Crear edición (staff) |
| GET | `editions/<pk>/` | Detalle + ruta GeoJSON + clima + media + clasificación |
| PATCH | `editions/<pk>/` | Editar edición (staff) |
| DELETE | `editions/<pk>/` | Eliminar edición (staff, solo si no ha comenzado) |
| POST | `editions/<pk>/register/` | Inscribirse |
| **POST** | **`editions/<pk>/activity/`** | **Subir track GPS + velocidad media** |
| GET/POST | `editions/<pk>/media/` | Listar / añadir media (POST: staff) |
| DELETE | `media/<pk>/` | Eliminar media (staff) |
| GET | `route-variants/` | Listar variantes de ruta |
| GET | `classifications/general/` | Ranking general (total + válidas por usuario) |
| GET | `stats/user/<pk>/` | Stats completas de un usuario |
| GET | `auth/strava/auth-url/` | URL de autorización Strava |
| POST | `auth/strava/connect/` | Conectar cuenta Strava |
| POST | `auth/strava/disconnect/` | Desconectar cuenta Strava |
| GET | `editions/<pk>/strava-activities/` | Actividades Ride del usuario en la fecha de la edición |
| POST | `editions/<pk>/activity/strava/` | Validar actividad Strava seleccionada |
| GET/POST | `strava/webhook/` | Strava Push Subscriptions |

### WebSocket
```
ws/tracking/<edition_id>/   →   TrackingConsumer
```

### Web accounts
| URL | Acción |
|-----|--------|
| `/accounts/strava/callback/` | Callback OAuth Strava (web) |
| `/accounts/strava/disconnect/` | Desconectar Strava (web, POST) |

### Dashboard (staff)
| URL | Acción |
|-----|--------|
| `/dashboard/editions/<pk>/publish/` | Publicar resultados manualmente |
| `/dashboard/editions/<pk>/media/add/` | Añadir foto/vídeo |
| `/dashboard/media/<pk>/delete/` | Borrar media |
| `/dashboard/activities/<pk>/validate/` | Toggle validación manual |
| `/dashboard/variants/new/` | Crear variante de ruta |

## Publicación de Resultados
`classifications/utils.py::recalculate_positions(edition)`:
1. Filtra `Activity` válidas de la edición, ordenadas por `elapsed_time_seconds`.
2. Calcula categoría con `get_category(birth_date, edition_date)`.
3. Crea/actualiza `Classification` con posición general y por categoría.
4. Se invoca automáticamente al recibir una actividad válida vía API (y la edición pasa a `results_published`).
5. También invocable manualmente desde el dashboard.

## App Móvil (`mobile/`)
Expo Router + TypeScript. Ver [mobile/README.md](mobile/README.md).

| Pantalla | Ruta | Acceso |
|----------|------|--------|
| Login / Registro | `(auth)/login`, `(auth)/register` | Público |
| Lista ediciones | `(tabs)/index` | Autenticado |
| Clasificación | `(tabs)/clasificacion` | Autenticado |
| Perfil + historial | `(tabs)/perfil` | Autenticado |
| Ruta + tracking GPS | `(tabs)/ruta` | Autenticado |
| Panel admin (tab) | `(tabs)/admin` | Solo staff |
| Admin: lista ediciones | `(tabs)/admin/index` | Solo staff |
| Admin: crear/editar edición | `(tabs)/admin/edition-form` | Solo staff |
| Admin: gestión de media | `(tabs)/admin/media-manager` | Solo staff |
| Detalle edición + mapa | `editions/[id]` | Autenticado |
| Tracking en vivo | `live/[id]` | Autenticado |

La subida del track se hace con `uploadActivity()` de `src/api/editions.ts`.

## Reglas de Desarrollo

1. **PostGIS nativo:** operaciones espaciales siempre en la BD, nunca Haversine en Python.
2. **Seguridad:** filtrar querysets por `request.user`; nunca aceptar `user` como input de serializer.
3. **Geometría:** `route_geojson` es `@property` calculada, no columna en BD. El track GPS no se persiste.
4. **Acceso:** todas las vistas web de ediciones y clasificaciones requieren `LoginRequired`. La `HomeView` es pública.
5. **Media:** fotos en `editions/media/`; vídeos como URL. `embed_url` convierte a embebible.
6. **Entorno Windows:** definir `GDAL_LIBRARY_PATH` y `GEOS_LIBRARY_PATH` en `settings/base.py`.
7. **`related_name` clave:** `participation.activity` (OneToOne).
8. **Validación GPS:** umbrales configurables en `settings` (`GPX_MATCH_THRESHOLD_METERS`, `GPX_MATCH_MIN_SCORE`).
9. **Auto-publicación:** al recibir una actividad válida la edición pasa a `results_published` automáticamente desde `ActivityUploadAPIView`.

## Despliegue (Dokploy)
- `docker-compose.yml`: `web` (Daphne ASGI, puerto 8000) + `worker` (Celery + Beat).
- `entrypoint.sh`: `web` ejecuta `migrate` + `collectstatic` + `daphne`; `worker` ejecuta `celery worker --beat`.
- BD y Redis son contenedores externos en `dokploy-network`.
- La BD **debe** usar imagen `postgis/postgis`.
- Volumen `media_data` compartido entre `web` y `worker`.

## GitHub y Flujo de Despliegue

- **Repositorio:** `https://github.com/ama9268/Clasica.git`
- **Rama de desarrollo:** `main`
- **Rama de producción:** `deploy` — es la que Dokploy escucha para disparar el redeploy automático.

### Workflow obligatorio para desplegar

Después de cada commit en `main`, ejecutar siempre:

```bash
git checkout deploy && git pull origin deploy && git merge main --no-edit && git push origin deploy && git checkout main
```

> **Nunca** hacer push directo a `deploy` con `--force`. La rama `deploy` solo recibe merges de `main`.
