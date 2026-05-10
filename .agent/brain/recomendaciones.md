# Recomendaciones de Mejora y Rendimiento

Este archivo contiene un listado de recomendaciones de refactorización y arquitectura para mantener el proyecto rápido, escalable y profesional.

- [x] **Índices Espaciales:** Implementar índices espaciales (SPGiST/GiST) estableciendo `spatial_index=True` (o verificándolo) en las geometrías de `Edition` y `StravaActivity` para maximizar el rendimiento.
- [x] **Integrar `rest_framework_gis`:** Refactorizar el serializador de la API para devolver GeoJSON de forma nativa utilizando `GeoFeatureModelSerializer` (o `GeometryField`), en lugar de utilizar un `@property` manual en los modelos.
- [ ] **Procesamiento de GPX Asíncrono:** Mover el parseo del archivo GPX (`_parse_gpx`) desde el hilo principal del Dashboard hacia una cola de tareas en segundo plano (ej. Celery, Redis) para evitar cuellos de botella en la interfaz con tracks pesados.
- [ ] **Downsampling del Perfil de Elevación:** Implementar un algoritmo (ej. guardar 1 de cada N puntos) antes de guardar la elevación en BD, para que Chart.js cargue el perfil más rápido en móviles si los GPX son muy pesados.
- [ ] **Caché Proactiva de AEMET:** Usar Celery Beat para recolectar la previsión de AEMET en background cada N horas, en lugar de esperar a que el usuario cargue la página y deba esperar a la API externa.
- [ ] **Lazy Loading de Gráficos/Mapas:** Inicializar Leaflet y Chart.js usando `IntersectionObserver` solo cuando el usuario haga scroll hacia ellos, ahorrando ancho de banda.
- [ ] **Validación de Geometría Proactiva:** Implementar un validador en el modelo `Activity` que asegure que el `track_geometry` no contenga puntos inválidos o ruidosos mediante un `pre_save hook`.
- [ ] **Seguridad de API de Tracking:** Implementar Rate Limiting y autenticación JWT estricta en los endpoints de recepción de coordenadas desde la App móvil.
- [ ] **Optimización de Consultas (Prefetch):** Asegurar el uso de `prefetch_related` en todas las vistas que listen inscripciones para evitar consultas N+1 al acceder a las actividades.
- [ ] **Modo Offline en la App:** Diseñar el sistema de sincronización para que la App móvil pueda guardar coordenadas localmente y subirlas por lotes (batch) cuando detecte conexión estable, mejorando la fiabilidad en zonas de montaña.
- [ ] **Migración a la Nueva Arquitectura:** Revisar la compatibilidad de todos los módulos nativos con la Nueva Arquitectura de React Native (habilitada por defecto en SDK 54).
- [ ] **Optimización de Bundle:** Utilizar `npx expo export` para analizar el tamaño del bundle y reducir dependencias innecesarias en el cliente móvil.
- [ ] **EAS Update:** Configurar `expo-updates` para permitir actualizaciones Over-The-Air (OTA) sin necesidad de que el usuario descargue una nueva versión de la tienda para cambios menores.
- [ ] **GitHub Actions para Despliegue Automático:** Configurar un workflow que automatice el despliegue al servidor cada vez que se realice un push o merge a la rama `deploy`.
- [ ] **Reglas de Protección de Rama:** Proteger la rama `deploy` para evitar pushes directos accidentales, requiriendo Pull Requests o aprobaciones.
- [ ] **Etiquetado de Versiones (Tags):** Utilizar etiquetas de Git (ej. `v1.0.0`) en la rama `deploy` para marcar hitos importantes de producción y facilitar rollbacks.
- [x] **Optimización de Docker (.dockerignore):** Crear archivo `.dockerignore` para excluir archivos innecesarios (venv, .git) y reducir el peso de la imagen de construcción.
- [x] **Estabilidad de Imagen Base:** Cambiar a `python:3.12-slim` para asegurar compatibilidad con wheels precompilados (evitando compilación lenta en 3.13).
- [x] **Sincronización de Rama `deploy`:** Mantener la rama `deploy` sincronizada con `main` únicamente cuando se desee realizar un despliegue a producción.
- [x] **Resolución de Conflictos de Puerto:** Usar el puerto 8002 para evitar colisiones con otros servicios en el mismo VPS.
- [ ] **Multi-stage Builds:** Implementar construcción multi-etapa en el Dockerfile para separar las dependencias de compilación del runtime final.
- [ ] **Health Checks en Docker:** Añadir `healthcheck` en `docker-compose.yml` para que Traefik/Dokploy solo envíen tráfico si la app está lista.
- [ ] **Endpoint de Salud en Django:** Crear `/api/health/` para validar conexiones críticas (DB, Redis) automáticamente.
- [ ] **Optimización de Daphne Workers:** Configurar el número de workers/hilos en el entrypoint para maximizar el rendimiento del VPS.
