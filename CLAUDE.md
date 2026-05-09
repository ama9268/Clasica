# Clasica — Prueba Ciclista Semanal

## Visión general

Aplicación para gestionar una prueba ciclista que se celebra cada miércoles.
Cada edición tiene una ruta diferente. Los participantes se registran; Strava
notifica automáticamente vía webhook cuando alguien sube una actividad que
coincide con la ruta oficial, y la app la importa sin intervención manual.
Durante la prueba, todos los participantes ven en tiempo real la posición del
resto en el mapa (móvil y web). Las clasificaciones y estadísticas son públicas.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Django 6.x + Django REST Framework |
| Base de datos | PostgreSQL + PostGIS (Docker externo en el VPS) |
| ORM geoespacial | GeoDjango (`django.contrib.gis`) |
| Frontend web | Django Templates + Tailwind CSS + HTMX 2.x + Alpine.js 3.x |
| Mapas web | Leaflet.js |
| Gráficas | Chart.js 4.x |
| Tiempo real | Django Channels 4.x + Daphne (ASGI) |
| Channel layer | Redis 7 |
| Cola de tareas | Celery 5.x (broker: Redis) |
| App móvil | React Native (Expo) — funcionalidad completa |
| Mapas móvil | `react-native-maps` / Expo Maps |
| Auth web | Sesiones Django |
| Auth API (móvil) | JWT (djangorestframework-simplejwt) |
| Strava | OAuth 2.0 (Strava API v3) + Webhook |
| Servidor | Daphne (ASGI, sustituye a Gunicorn) + WhiteNoise |
| Deploy | Dokploy (Docker Compose en VPS) |

---

## Estructura del proyecto

```
clasica/
├── manage.py
├── requirements.txt
├── entrypoint.sh
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── tailwind.config.js
├── clasica_project/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── asgi.py               ← routing HTTP + WebSocket
│   ├── celery.py
│   └── urls.py
└── apps/
    ├── accounts/             # Registro, login, perfil, Strava OAuth
    ├── editions/             # Ediciones semanales, GPX oficial (PostGIS)
    ├── participations/       # Inscripción, webhook Strava, import automático
    ├── classifications/      # Clasificaciones calculadas y stats
    ├── tracking/             # Seguimiento en tiempo real (Channels WebSocket)
    ├── dashboard/            # Panel web organizador (staff only)
    └── api/                  # Endpoints DRF para la app móvil
```

---

## Modelos principales

### accounts.UserProfile (extiende AbstractUser)
- `full_name` — nombre completo (visible en clasificaciones)
- `birth_date` — fecha de nacimiento (para asignar categoría automáticamente)
- `photo` — foto de perfil (ImageField)
- `club` — club o equipo
- `strava_athlete_id` — ID del atleta en Strava
- `strava_access_token`, `strava_refresh_token`, `strava_token_expires_at`
  — tokens OAuth; **nunca exponer en API ni serializer**

### editions.Edition
- `date` — fecha del miércoles (unique, `db_index=True`)
- `name` — nombre descriptivo
- `route_gpx` — archivo GPX original (FileField, para descarga)
- `route_geometry` — `LineStringField(srid=4326)` — geometría PostGIS de la ruta
- `route_distance_km` — calculado al subir el GPX
- `status` — `open` | `closed` | `results_published`
- Propiedad `is_registration_open`

### participations.Participation
- `user` FK → UserProfile (`db_index=True`)
- `edition` FK → Edition
- `registered_at`
- Unique together: (user, edition)

### participations.StravaActivity
- `participation` OneToOne → Participation
- `strava_activity_id` — ID en Strava
- `elapsed_time_seconds` — tiempo total
- `track_geometry` — `LineStringField(srid=4326)` — geometría PostGIS del track
- `is_valid` — True si supera la validación geoespacial
- `validation_score` — porcentaje de coincidencia con la ruta oficial (0.0–1.0)
- `imported_at`

### classifications.Classification
- `participation` OneToOne → Participation
- `time_seconds` — tiempo efectivo (solo si `is_valid`)
- `category` — `open` | `m40` | `m50` | `m60` (`db_index=True`)
- `position_overall` — posición en clasificación general de la edición
- `position_category` — posición en su categoría
- Se recalcula al validar/invalidar una actividad

---

## Categorías de edad

La categoría se calcula en el momento de crear `Classification`,
**no se almacena en el perfil del usuario**:

| Categoría | Rango de edad en la fecha de la edición |
|---|---|
| M60+ | ≥ 60 años |
| M50 | 50–59 años |
| M40 | 40–49 años |
| Open/Elite | < 40 años |

```python
def get_category(birth_date: date, edition_date: date) -> str:
    age = (edition_date - birth_date).days // 365
    if age >= 60: return 'm60'
    if age >= 50: return 'm50'
    if age >= 40: return 'm40'
    return 'open'
```

---

## Integración Strava

### Conceptos clave
- **Webhook**: una única suscripción a nivel de app (no por usuario). Todos los
  eventos de todos los usuarios conectados llegan al mismo endpoint.
- **OAuth por usuario**: obligatorio al menos una vez. El webhook notifica, pero
  para obtener los datos GPS se necesita el `access_token` almacenado del usuario.
- **Payload del webhook**: solo contiene `object_id` (activity ID) y `owner_id`
  (Strava athlete ID). No incluye GPS ni tipo de deporte.
- **Rate limit Strava**: 200 req/15 min, 2 000 req/día (por app). Procesar en
  background (Celery) para no bloquear el webhook y respetar los límites.

### Flujo OAuth (una vez por usuario)
1. Usuario hace clic en "Conectar Strava" → redirige a `https://www.strava.com/oauth/authorize`
2. Scope requerido: `activity:read_all`
3. Strava redirige a `/accounts/strava/callback/?code=XXX`
4. App intercambia `code` por tokens y guarda en `UserProfile`
5. A partir de ahí, los webhooks de ese usuario se procesan automáticamente

### Flujo webhook (auto-importación)
1. Strava envía `POST /webhooks/strava/` con `{"object_id": X, "owner_id": Y, "aspect_type": "create"}`
2. Vista valida la firma `X-Strava-Signature` (HMAC-SHA256 con `STRAVA_CLIENT_SECRET`)
3. Responde `200 OK` en < 2 s y **encola tarea Celery** `process_strava_webhook`
4. La tarea Celery:
   a. Busca el `UserProfile` por `strava_athlete_id == owner_id`
   b. Refresca el access token si caduca en < 5 min
   c. Llama `GET /activities/{object_id}` → comprueba que es tipo cycling y fecha = miércoles activo
   d. Llama `GET /activities/{object_id}/streams?keys=latlng` → extrae coordenadas
   e. Construye `LineString` y llama a validación GPS (ver abajo)
   f. Guarda `StravaActivity`; si válido, crea/actualiza `Classification`

### Registro del webhook (una vez, a nivel de app)
```bash
# Management command: python manage.py register_strava_webhook
POST https://www.strava.com/api/v3/push_subscriptions
  client_id, client_secret, callback_url, verify_token
```
El endpoint de verificación responde al challenge GET que envía Strava:
```python
# GET /webhooks/strava/?hub.mode=subscribe&hub.challenge=XXX&hub.verify_token=YYY
return JsonResponse({"hub.challenge": request.GET["hub.challenge"]})
```

### Refresco de token
```python
# apps/accounts/strava.py
def get_valid_access_token(user: UserProfile) -> str:
    if user.strava_token_expires_at - now() < timedelta(minutes=5):
        # POST https://www.strava.com/oauth/token con grant_type=refresh_token
        ...
    return user.strava_access_token
```

---

## Validación GPS con PostGIS

La validación compara el `LineString` del usuario con el `LineString` oficial
usando la función `ST_FrechetDistance` de PostGIS (más precisa que un loop Python).

```python
# apps/participations/validators.py
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import LineString

def validate_track(edition: Edition, user_track: LineString) -> tuple[bool, float]:
    """
    Retorna (is_valid, score 0.0–1.0).
    Densifica el track oficial cada 50 m y calcula qué porcentaje de esos
    puntos tiene un punto del track usuario a < GPX_MATCH_THRESHOLD_METERS.
    """
    ...
```

Umbrales configurables en `settings/base.py`:
```python
GPX_MATCH_THRESHOLD_METERS = 100
GPX_MATCH_MIN_SCORE = 0.80
```

---

## Seguimiento en tiempo real (app tracking)

Durante la prueba los participantes envían su posición GPS y todos los ciclistas
de esa edición aparecen en el mapa en tiempo real.

### Arquitectura
- **Django Channels `TrackingConsumer`**: WebSocket en `ws://.../ws/tracking/{edition_id}/`
- **Redis** como channel layer: `CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", ...}}`
- Las posiciones son **efímeras** (no se persisten en BD); se almacenan en el
  grupo de Channels `edition_{id}` mientras la conexión está activa
- Al desconectar, el cliente deja de aparecer en el mapa

### Flujo
1. Móvil abre WebSocket autenticado (JWT en header `Sec-WebSocket-Protocol`)
2. `TrackingConsumer.connect()` verifica JWT y `Participation` activa → `accept()`
3. Móvil envía posición cada 10 s: `{"lat": 41.123, "lng": 2.456, "speed": 28.5}`
4. Consumer hace `broadcast` al grupo `edition_{id}` con `{"user_id": X, "lat": ..., "lng": ..., "speed": ...}`
5. Todos los conectados (web + móvil) reciben la actualización y actualizan el marcador en el mapa

### Mapa web (Leaflet.js)
- Un marcador por participante conectado; se actualiza con cada mensaje WebSocket
- Polyline de la ruta oficial superpuesta (cargada desde `edition.route_gpx`)

### Mapa móvil (react-native-maps)
- `MapView` con marcadores dinámicos; mapa seguido del usuario propio
- Misma conexión WebSocket que la web

### URLs de Channels (asgi.py)
```python
websocket_urlpatterns = [
    path("ws/tracking/<int:edition_id>/", TrackingConsumer.as_asgi()),
]
```

---

## API REST (para la app móvil)

Todos los endpoints bajo `/api/v1/`. Auth: JWT Bearer token.

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/v1/auth/register/` | Registro |
| POST | `/api/v1/auth/login/` | Login → tokens JWT |
| POST | `/api/v1/auth/token/refresh/` | Refrescar JWT |
| GET/PATCH | `/api/v1/auth/me/` | Perfil propio |
| GET | `/api/v1/editions/` | Lista de ediciones |
| GET | `/api/v1/editions/{id}/` | Detalle + clasificación + GeoJSON ruta |
| POST | `/api/v1/editions/{id}/register/` | Inscribirse en edición |
| GET | `/api/v1/classifications/general/` | Clasificación acumulada general |
| GET | `/api/v1/stats/user/{id}/` | Stats individuales |
| GET | `/api/v1/strava/connect/` | URL de autorización OAuth Strava |
| POST | `/api/v1/strava/disconnect/` | Desconectar cuenta Strava |
| GET/POST | `/webhooks/strava/` | Webhook Strava (challenge + eventos) |

Las clasificaciones y stats son de solo lectura sin autenticación
(`IsAuthenticatedOrReadOnly`).

---

## Frontend web (Tailwind CSS + responsivo)

- **Tailwind CSS** vía CLI standalone (no Node.js en Docker); compilar con
  `tailwindcss -i ./static/src/main.css -o ./static/dist/main.css --minify`
- Diseño **mobile-first** y completamente responsivo
- `tailwind.config.js` con `content: ["./templates/**/*.html", "./apps/**/*.py"]`
- WhiteNoise sirve los ficheros estáticos compilados en producción
- Leaflet.js cargado desde CDN para mapas en vistas públicas

---

## Panel web del organizador (dashboard app)

Vistas protegidas con `StaffRequiredMixin`:

- **Lista de ediciones** — ver todas, cambiar estado
- **Crear edición** — fecha, nombre, subir GPX → parsea y guarda `route_geometry`
- **Detalle edición** — participantes, actividades, override manual de `is_valid`
- **Publicar resultados** — estado `results_published`, recalcula posiciones

---

## Vistas públicas (web, sin login)

- **Inicio** — próxima edición + últimas clasificaciones
- **Edición** — clasificación + mapa de la ruta (Leaflet) + Chart.js por categorías
- **Perfil público** — estadísticas individuales + histórico
- **Clasificación general** — tabla acumulada de todas las ediciones
- **Mapa en vivo** — durante la prueba, mapa Leaflet con posiciones en tiempo real

---

## Reglas de desarrollo

1. **Filtrar siempre por usuario**: `qs.filter(user=request.user)` en vistas privadas
2. **`user` nunca en serializer**: se asigna en `perform_create(self, serializer)`
3. **Tokens Strava en `.env`**: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_VERIFY_TOKEN`. Nunca en código
4. **Categoría calculada en el momento**: no almacenar en perfil, calcular al crear `Classification`
5. **Webhook responde en < 2 s**: toda la lógica va en una tarea Celery, el view solo encola
6. **Validar firma del webhook**: usar `hmac.compare_digest` (tiempo constante) con `STRAVA_CLIENT_SECRET`
7. **CBVs con Mixins**: `LoginRequiredMixin` para web, `IsAuthenticated` para API
8. **WebSocket auth en `connect()`**: verificar JWT y `Participation` antes de `accept()`
9. **Settings por entorno**: `base.py` + `development.py` + `production.py`
10. **Logging estructurado**: `logger = logging.getLogger(__name__)`, no `print()`
11. **Type hints** en todas las funciones nuevas
12. **PostGIS siempre en `srid=4326`** (WGS-84, coordenadas GPS estándar)

---

## Despliegue (Dokploy)

Dos servicios propios: `web` (Daphne ASGI) y `worker` (Celery).
**Redis y PostgreSQL son contenedores externos ya existentes en el VPS** —
no se declaran en este compose; se referencian por sus URLs en `.env`.

```yaml
services:
  web:
    build: .
    restart: unless-stopped
    env_file: .env
    environment:
      SERVICE: web
    volumes:
      - media_data:/app/media
      - static_data:/app/staticfiles
    ports:
      - "8000:8000"
    networks:
      - dokploy-network

  worker:
    build: .
    restart: unless-stopped
    env_file: .env
    environment:
      SERVICE: worker
    networks:
      - dokploy-network

volumes:
  media_data:
  static_data:

networks:
  dokploy-network:
    external: true
```

### entrypoint.sh
```bash
#!/bin/bash
set -e
if [ "$SERVICE" = "worker" ]; then
    exec celery -A clasica_project worker -l info
else
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    # Compilar Tailwind si es necesario
    # tailwindcss -i ./static/src/main.css -o ./static/dist/main.css --minify
    exec daphne -b 0.0.0.0 -p 8000 clasica_project.asgi:application
fi
```

### Variables de entorno requeridas

```
SECRET_KEY=
DEBUG=False
ALLOWED_HOSTS=
DATABASE_URL=postgresql://user:pass@<host-o-container>:5432/Clasica
REDIS_URL=redis://default:<password>@<host-o-container>:6379
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_VERIFY_TOKEN=        # token arbitrario para validar el webhook
STRAVA_REDIRECT_URI=https://tudominio.com/accounts/strava/callback/
```

> `DATABASE_URL` usa esquema `postgis://` (no `postgresql://`) para que
> GeoDjango detecte PostGIS automáticamente.

### Dependencias del sistema (Dockerfile)
```dockerfile
RUN apt-get install -y gdal-bin libgdal-dev libgeos-dev libproj-dev
```
GeoDjango necesita GDAL, GEOS y PROJ en el sistema.

---

## Dependencias clave (requirements.txt)

```
django>=6.0
djangorestframework
djangorestframework-simplejwt
psycopg2-binary           # incluye soporte PostGIS vía libpq
daphne
channels[daphne]
channels-redis
celery[redis]
whitenoise
Pillow
gpxpy                     # parseo inicial de GPX al subir la ruta oficial
requests
django-environ
```

---

## PostGIS: habilitar extensión en la BD

Al crear la BD por primera vez (una sola vez, como superusuario):
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```
O desde Django: crear una migración inicial en cualquier app con:
```python
from django.contrib.postgres.operations import CreateExtension
operations = [CreateExtension("postgis")]
```

---

## Verificación

```bash
# Tests unitarios
python manage.py test apps.participations.tests   # validación GPS
python manage.py test apps.classifications.tests  # categorías y posiciones
python manage.py test apps.tracking.tests         # consumer WebSocket

# Endpoints
GET  /api/v1/editions/                        # sin token → 200 OK
POST /api/v1/editions/1/register/             # sin token → 401
GET  /webhooks/strava/?hub.mode=subscribe&hub.challenge=TEST&hub.verify_token=XXX  # → {"hub.challenge": "TEST"}

# WebSocket (wscat)
wscat -c ws://localhost:8000/ws/tracking/1/ -H "Sec-WebSocket-Protocol: jwt,<token>"
```

---

## Nota sobre el CLAUDE.md global vs. por app

El **CLAUDE.md global** (`~/.claude/CLAUDE.md`) recoge los patrones de despliegue
con Dokploy reutilizables en todos los proyectos. **No es necesario modificarlo**
para este proyecto: la estructura `web + worker + redis` encaja perfectamente en
el patrón `docker-compose.yml` ya documentado, simplemente añadiendo el servicio
`redis` y usando Daphne en lugar de Gunicorn.

No se crean CLAUDE.md por app individual: la complejidad del proyecto no lo
justifica. Un único CLAUDE.md en la raíz es suficiente y más fácil de mantener.
