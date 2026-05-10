# La Clásica — App Móvil

App React Native (Expo) para la prueba ciclista semanal.

## Setup

```bash
cd mobile
cp .env.example .env          # ajusta las URLs al backend
npm install
npx expo start
```

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `EXPO_PUBLIC_API_BASE_URL` | URL de la API REST Django (ej. `http://192.168.1.x:8000/api/v1`) |
| `EXPO_PUBLIC_WS_BASE_URL` | URL base WebSocket (ej. `ws://192.168.1.x:8000`) |

> En Android Emulator usa `10.0.2.2` en vez de `localhost`.

## Estructura

```
app/
  (auth)/login.tsx        # Inicio de sesión
  (auth)/register.tsx     # Registro
  (tabs)/index.tsx        # Lista de ediciones
  (tabs)/clasificacion.tsx # Clasificación general
  (tabs)/perfil.tsx       # Perfil y stats del usuario
  editions/[id].tsx       # Detalle de edición + mapa de ruta
  live/[id].tsx           # Tracking en vivo por WebSocket
src/
  api/                    # Llamadas al backend (JWT auto-refresh)
  context/AuthContext.tsx # Estado de autenticación global
  hooks/useTracking.ts    # WebSocket + posiciones en tiempo real
  types/index.ts          # Tipos TypeScript
```
