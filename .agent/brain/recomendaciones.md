# Recomendaciones de Mejora y Rendimiento

Listado vivo de mejoras arquitectónicas, de seguridad y rendimiento. Ordenado por urgencia.
Las marcadas con **🔴 URGENTE** tienen impacto directo en producción y deben implementarse pronto.

---

## 🔴 URGENTES — Implementar Ya

- [x] **🔴 Tests Unitarios e Integración:** 33 tests implementados: `get_category` (7), `recalculate_positions` (4), `validate_track` con PostGIS real (5), `ActivityUploadAPIView` (7), `RegisterAPIView`+`EditionRegisterAPIView` (6), `auto_close_expired_editions` con freezegun (4). Cobertura ~52%. Ejecutar con `pytest`.

- [x] **🔴 Rate Limiting en la API:** Throttling nativo DRF con Redis DB1 como caché compartido. Login 10/min, register 5/h, activity_upload 10/h, webhook 200/min, global anon 30/min, user 100/min. 4 tests de throttling añadidos (37 total).

- [x] **🔴 Validación Estricta de Inputs en Activity Upload:** `ActivityUploadSerializer` con `elapsed_time_seconds` (1–64800 s), `average_moving_speed` (0.1–120 km/h), y validación de coordenadas GeoJSON (tipo, rango lon/lat, mínimo 2 puntos). 9 tests de validación añadidos (46 total).

- [x] **🔴 Monitorización de Errores (Sentry):** `sentry-sdk[django]` añadido a `requirements.txt`. Configuración en `settings/base.py` condicional a `SENTRY_DSN` (inactivo sin DSN → no rompe local ni tests). Añadir `SENTRY_DSN=<dsn>` en Dokploy para activar en producción.

- [x] **🔴 Endpoint de Salud `/api/health/`:** `HealthCheckAPIView` en `/api/health/` verifica BD y caché. Devuelve 200/503 según estado. `healthcheck` añadido al servicio `web` en `docker-compose.yml` (intervalo 30s, start_period 60s). 4 tests añadidos (50 total).

- [x] **🔴 Optimización de Consultas N+1:** `select_related("route_variant")` en `EditionListAPIView` y `EditionDetailAPIView` (+ `prefetch_related("media")`). `UserStatsSerializer` evalúa el queryset una sola vez (lista cacheada en context) eliminando 2 COUNT extras. Tests con `django_assert_num_queries` verifican 1 query para lista y 2 para stats (52 total).

---

## 🟠 ALTA PRIORIDAD — Sprint Próximo

- [ ] **Firma de Webhook Strava:** El endpoint `POST /strava/webhook/` acepta cualquier payload sin verificar la firma `X-Hub-Signature-256` que envía Strava. Un atacante puede inyectar eventos falsos. Implementar la verificación HMAC-SHA256 con `STRAVA_CLIENT_SECRET` antes de procesar el cuerpo.

- [ ] **Circuit Breaker para AEMET:** Si AEMET falla o tarda, la respuesta de `EditionDetailSerializer` bloquea el hilo Django. Añadir un timeout explícito (`requests.get(..., timeout=5)`) y un fallback que devuelva `None` sin relanzar la excepción. Complementar con el cache ya existente para servir el último dato válido aunque AEMET esté caída.

- [ ] **Health Checks en Docker Compose:** Sin `healthcheck` en `docker-compose.yml`, Dokploy puede marcar el contenedor como "up" aunque la app tarde 30 s en arrancar (pendiente de migrate). Añadir:
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  ```

- [ ] **Paginación en Endpoints de Lista API:** `EditionListAPIView` devuelve todas las ediciones de golpe; con el tiempo la respuesta crecerá indefinidamente. Activar `PageNumberPagination` de DRF con `page_size=20`.

- [ ] **Procesamiento de GPX Asíncrono:** En `EditionListAPIView.post` y `EditionDetailAPIView.patch` se llama a `parse_gpx_to_geometry_and_elevation` de forma síncrona en el hilo de request. Un GPX pesado puede bloquear el worker de Daphne durante segundos. Mover a una tarea Celery que actualice `edition` en background.

- [ ] **Cabeceras de Seguridad HTTP:** En producción no se fuerzan cabeceras básicas. Añadir en `settings/production.py`:
  ```python
  SECURE_SSL_REDIRECT = True
  SECURE_HSTS_SECONDS = 31536000
  SESSION_COOKIE_SECURE = True
  CSRF_COOKIE_SECURE = True
  X_FRAME_OPTIONS = "DENY"
  ```

- [ ] **Logging Estructurado:** Los `logger.warning` actuales en `api/views.py` son texto plano. En producción es difícil filtrar por `user_id` o `edition_id`. Usar `structlog` o añadir `extra={"user_id": ..., "edition_id": ...}` a los llamados de logging para facilitar debug en producción.

---

## 🟡 MEDIA PRIORIDAD — Planificar

- [ ] **Modo Offline en la App Móvil:** En zonas de montaña la conexión puede perderse durante la prueba. Diseñar el sistema para que `useTracking.ts` almacene las coordenadas en `AsyncStorage` y las envíe en batch cuando detecte conexión estable, en lugar de perder el track si se corta.

- [ ] **EAS Update (OTA):** Configurar `expo-updates` para permitir actualizaciones Over-The-Air sin que el usuario deba descargar una nueva versión de la tienda. Ideal para correcciones de bugs urgentes en la app.

- [ ] **Downsampling del Perfil de Elevación:** Si el GPX tiene miles de puntos, el JSON de `elevation_profile` puede ser muy pesado para Chart.js en móviles. Implementar un algoritmo de reducción (Ramer-Douglas-Peucker o simplemente 1 de cada N puntos) antes de persistir en BD.

- [ ] **Caché Proactiva de AEMET con Celery Beat:** En lugar de llamar a AEMET cuando el usuario carga la página, agregar una tarea Beat que actualice el pronóstico cada hora para las ediciones `open`. Así la respuesta siempre viene de caché y AEMET nunca es un cuello de botella en el request.

- [ ] **Multi-stage Builds en Dockerfile:** Separar la fase de compilación (build tools, headers C) de la imagen final para reducir el tamaño del contenedor de producción. Puede reducir la imagen ~200–300 MB.

- [ ] **Optimización de Bundle Móvil:** Ejecutar `npx expo export` + `@expo/bundle-analyzer` para identificar dependencias pesadas innecesarias. Evaluar si `react-native-maps` y librerías de geolocalización están correctamente tree-shaken.

- [ ] **Migración a Nueva Arquitectura React Native:** La Nueva Arquitectura (Fabric + TurboModules) está habilitada por defecto en Expo SDK 54+. Verificar compatibilidad de `react-native-maps`, `expo-location` y `react-native-background-fetch` para evitar fallos silenciosos.

- [ ] **Validación de Geometría Proactiva:** Añadir un `pre_save` signal o validador en el modelo que compruebe que el track enviado no contenga coordenadas nulas, duplicadas o fuera de rango (lat ∈ [-90,90], lon ∈ [-180,180]) antes de pasarlo a `validate_track`.

---

## 🟢 BAJA PRIORIDAD — Mejoras de Calidad

- [ ] **Reglas de Protección de Rama:** Proteger la rama `deploy` en GitHub para evitar pushes directos accidentales. Requerir que los cambios lleguen solo mediante merge de `main`.

- [ ] **Etiquetado de Versiones (Tags):** Usar `git tag v1.x.x` en la rama `deploy` para marcar hitos de producción y poder hacer rollback limpio (`git checkout v1.0.0`).

- [ ] **Iconos Dinámicos de Clima:** Los iconos de estado del cielo en el detalle de edición son estáticos. Mapear los códigos de `estado_cielo` de AEMET a íconos SVG correspondientes (sol, nubes, lluvia, tormenta) para mejorar la UX sin coste adicional.

- [ ] **Skeleton Loaders en la App Móvil:** Las pantallas de lista de ediciones y clasificación muestran un spinner genérico durante la carga. Reemplazar con skeletons que reflejen la estructura real de las cards para mejorar la percepción de velocidad.

- [ ] **Validación de Fortaleza de Contraseña:** Añadir `AUTH_PASSWORD_VALIDATORS` de Django en producción y feedback visual en tiempo real en el formulario de registro de la app móvil y web.

- [ ] **Notificaciones de Seguridad por Email:** Enviar un email automático al usuario cuando ocurra un cambio sensible en su cuenta (cambio de contraseña, desconexión de Strava, nuevo login desde IP diferente).

- [ ] **Detección Automática de Cimas:** Procesar el GPX de la ruta para identificar puertos o cimas (punto local de máxima altitud seguido de descenso sostenido) y mostrarlos como hitos en el mapa del detalle de edición.

- [ ] **Paginación en el Dashboard de Administración:** El listado de ediciones del panel staff no tiene paginación. Con el tiempo puede volverse lento. Activar `paginate_by = 20` en la vista correspondiente.

- [ ] **Optimización de Daphne Workers:** Ajustar `--workers` y `--threads` en `entrypoint.sh` en función de los cores del VPS. Para un VPS de 2 vCPU: `daphne ... -u /tmp/daphne.sock --access-log - --proxy-headers` con proxy Nginx es la configuración más eficiente.

---

## ✅ Completadas

- [x] **Índices Espaciales** — `spatial_index=True` en geometrías de Edition y RouteVariant.
- [x] **Integrar `rest_framework_gis`** — `route_geojson` devuelto como GeoJSON nativo.
- [x] **GitHub Actions para Despliegue Automático** — Workflow configurado en la rama `deploy`.
- [x] **Optimización de Docker (.dockerignore)** — Archivo creado, imagen más ligera.
- [x] **Estabilidad de Imagen Base** — `python:3.12-slim` en el Dockerfile.
- [x] **Sincronización de Rama `deploy`** — Flujo main → deploy documentado en CLAUDE.md.
- [x] **Resolución de Conflictos de Puerto** — Puerto 8010 en producción.
- [x] **Validación Robusta de API AEMET** — Pydantic/validación de estructura de respuesta.
- [x] **Optimización de Imágenes con WebP** — `optimize_image()` en `UserProfile.save()` y `EditionMedia.save()`.
- [x] **Compresión de Imágenes en Cliente** — `expo-image-manipulator` antes de subir fotos.
- [x] **Gestión de Túneles Expo** — `@expo/ngrok` instalado localmente.
