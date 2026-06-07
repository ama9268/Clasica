import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import * as Location from 'expo-location';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { GeoJSONLineString, RutaPoint } from '../types';
import { LOCATION_TASK, BUFFER_KEY } from '../tasks/locationTask';

const SYNC_INTERVAL_MS = 5_000;

export interface RutaState {
  tracking: boolean;
  elapsedSeconds: number;
  currentSpeed: number;
  avgMovingSpeed: number;
  pointCount: number;
}

export interface RutaResult {
  track_geojson: GeoJSONLineString;
  elapsed_time_seconds: number;
  average_moving_speed: number | null;
}

export function useRuta(sendPosition: (lat: number, lng: number, speed: number) => void) {
  const [tracking, setTracking] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [currentSpeed, setCurrentSpeed] = useState(0);
  const [avgMovingSpeed, setAvgMovingSpeed] = useState(0);
  const [pointCount, setPointCount] = useState(0);

  const buffer = useRef<RutaPoint[]>([]);
  const startTime = useRef<number>(0);
  const syncedCount = useRef(0);
  const syncInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const clockInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const appStateRef = useRef<AppStateStatus>(AppState.currentState);
  const trackingRef = useRef(false); // ref mirror to avoid stale closure in AppState handler

  // ── Sync de AsyncStorage → estado React + WS ────────────────────────────────

  const syncFromStorage = useCallback(async () => {
    try {
      const raw = await AsyncStorage.getItem(BUFFER_KEY);
      if (!raw) return;
      const all: RutaPoint[] = JSON.parse(raw);
      const newPts = all.slice(syncedCount.current);
      if (newPts.length === 0) return;

      for (const pt of newPts) {
        buffer.current.push(pt);
        try { sendPosition(pt.lat, pt.lon, pt.speed_kmh); } catch { /* WS caído */ }
      }
      syncedCount.current = all.length;

      const movingPts = buffer.current.filter((p) => p.speed_kmh > 0);
      const avg = movingPts.length
        ? movingPts.reduce((s, p) => s + p.speed_kmh, 0) / movingPts.length
        : 0;
      const last = buffer.current[buffer.current.length - 1];
      setCurrentSpeed(last?.speed_kmh ?? 0);
      setAvgMovingSpeed(avg);
      setPointCount(buffer.current.length);
    } catch {
      // error de storage
    }
  }, [sendPosition]);

  function startSyncInterval() {
    if (syncInterval.current) return;
    syncInterval.current = setInterval(syncFromStorage, SYNC_INTERVAL_MS);
  }

  function stopSyncInterval() {
    if (syncInterval.current) {
      clearInterval(syncInterval.current);
      syncInterval.current = null;
    }
  }

  // ── AppState: retomar sync al volver a primer plano ─────────────────────────

  useEffect(() => {
    const sub = AppState.addEventListener('change', (nextState: AppStateStatus) => {
      const wasActive = appStateRef.current === 'active';
      const isActive = nextState === 'active';
      appStateRef.current = nextState;

      if (!trackingRef.current) return;

      if (isActive && !wasActive) {
        // Vuelve al primer plano: sincronizar puntos acumulados en background
        syncFromStorage();
        startSyncInterval();
      } else if (!isActive && wasActive) {
        // Va al background: detener sync (la tarea nativa sigue capturando GPS)
        stopSyncInterval();
      }
    });
    return () => sub.remove();
  }, [syncFromStorage]);

  // ── API pública ─────────────────────────────────────────────────────────────

  const watchSub = useRef<Location.LocationSubscription | null>(null);

  async function startTracking(): Promise<boolean> {
    const { status: fgStatus } = await Location.requestForegroundPermissionsAsync();
    if (fgStatus !== 'granted') return false;

    try {
      await Location.requestBackgroundPermissionsAsync();
    } catch {
      // permisos background no disponibles en este entorno
    }

    // Limpiar estado anterior
    await AsyncStorage.removeItem(BUFFER_KEY);
    buffer.current = [];
    syncedCount.current = 0;
    startTime.current = Date.now();
    setElapsedSeconds(0);
    setCurrentSpeed(0);
    setAvgMovingSpeed(0);
    setPointCount(0);

    // Detener tarea previa si quedó colgada
    if (await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK)) {
      await Location.stopLocationUpdatesAsync(LOCATION_TASK);
    }

    try {
      await Location.startLocationUpdatesAsync(LOCATION_TASK, {
        accuracy: Location.Accuracy.High,
        timeInterval: 5000,
        distanceInterval: 10,
        showsBackgroundLocationIndicator: true,
        foregroundService: {
          notificationTitle: 'La Clásica — Ruta activa',
          notificationBody: 'Registrando tu recorrido GPS...',
          notificationColor: '#8b1a1a',
        },
      });
    } catch {
      // Expo Go no soporta background tasks en iPhone físico — fallback a foreground

      // Punto inicial inmediato para que siempre haya ≥1 punto desde el arranque
      const initial = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      const initialPt = {
        lon: initial.coords.longitude,
        lat: initial.coords.latitude,
        speed_kmh: Math.max(0, (initial.coords.speed ?? 0) * 3.6),
        timestamp: initial.timestamp,
      };
      await AsyncStorage.setItem(BUFFER_KEY, JSON.stringify([initialPt]));

      watchSub.current = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.High, timeInterval: 5000, distanceInterval: 10 },
        async (loc) => {
          const pt = {
            lon: loc.coords.longitude,
            lat: loc.coords.latitude,
            speed_kmh: Math.max(0, (loc.coords.speed ?? 0) * 3.6),
            timestamp: loc.timestamp,
          };
          const raw = await AsyncStorage.getItem(BUFFER_KEY);
          const buf = raw ? JSON.parse(raw) : [];
          buf.push(pt);
          await AsyncStorage.setItem(BUFFER_KEY, JSON.stringify(buf));
        }
      );
    }

    trackingRef.current = true;
    setTracking(true);

    await syncFromStorage();
    startSyncInterval();

    clockInterval.current = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime.current) / 1000));
    }, 1000);

    return true;
  }

  async function stopTracking(): Promise<RutaResult | null> {
    if (watchSub.current) {
      watchSub.current.remove();
      watchSub.current = null;
    } else if (await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK)) {
      await Location.stopLocationUpdatesAsync(LOCATION_TASK);
    }

    stopSyncInterval();
    if (clockInterval.current) {
      clearInterval(clockInterval.current);
      clockInterval.current = null;
    }

    trackingRef.current = false;
    setTracking(false);

    // Sync final para no perder los últimos puntos
    await syncFromStorage();
    await AsyncStorage.removeItem(BUFFER_KEY);

    const pts = buffer.current;
    if (pts.length < 2) return null;

    const sorted = [...pts].sort((a, b) => a.timestamp - b.timestamp);
    const coords: [number, number][] = sorted.map((p) => [p.lon, p.lat]);
    const elapsed = Math.floor((Date.now() - startTime.current) / 1000);
    const movingPts = sorted.filter((p) => p.speed_kmh > 0);
    const avgSpeed = movingPts.length
      ? movingPts.reduce((s, p) => s + p.speed_kmh, 0) / movingPts.length
      : null;

    return {
      track_geojson: { type: 'LineString', coordinates: coords },
      elapsed_time_seconds: elapsed,
      average_moving_speed: avgSpeed !== null ? Math.round(avgSpeed * 10) / 10 : null,
    };
  }

  // Limpieza al desmontar
  useEffect(() => {
    return () => {
      stopSyncInterval();
      if (clockInterval.current) clearInterval(clockInterval.current);
      if (watchSub.current) { watchSub.current.remove(); watchSub.current = null; }
    };
  }, []);

  return {
    state: { tracking, elapsedSeconds, currentSpeed, avgMovingSpeed, pointCount } as RutaState,
    startTracking,
    stopTracking,
  };
}
