import { useCallback, useEffect, useRef, useState } from 'react';
import * as Location from 'expo-location';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { GeoJSONLineString, RutaPoint } from '../types';

const OFFLINE_QUEUE_KEY = '@clasica/offline_positions';
const CAPTURE_INTERVAL_MS = 5_000;

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
  const captureInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const clockInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const capturePosition = useCallback(async () => {
    try {
      const loc = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      const speed_kmh = Math.max(0, (loc.coords.speed ?? 0) * 3.6);
      const point: RutaPoint = {
        lon: loc.coords.longitude,
        lat: loc.coords.latitude,
        speed_kmh,
        timestamp: loc.timestamp,
      };
      buffer.current = [...buffer.current, point];

      // Recalculate avg moving speed from buffer
      const movingPts = buffer.current.filter((p) => p.speed_kmh > 0);
      const avg = movingPts.length
        ? movingPts.reduce((s, p) => s + p.speed_kmh, 0) / movingPts.length
        : 0;
      setCurrentSpeed(speed_kmh);
      setAvgMovingSpeed(avg);
      setPointCount(buffer.current.length);

      // Try WebSocket; on failure queue offline
      try {
        sendPosition(point.lat, point.lon, speed_kmh);
      } catch {
        await enqueueOffline(point);
      }
    } catch {
      // GPS unavailable
    }
  }, [sendPosition]);

  async function enqueueOffline(point: RutaPoint) {
    try {
      const raw = await AsyncStorage.getItem(OFFLINE_QUEUE_KEY);
      const queue: RutaPoint[] = raw ? JSON.parse(raw) : [];
      queue.push(point);
      await AsyncStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
    } catch {
      // storage error, point lost
    }
  }

  async function flushOfflineQueue() {
    try {
      const raw = await AsyncStorage.getItem(OFFLINE_QUEUE_KEY);
      if (!raw) return;
      const queue: RutaPoint[] = JSON.parse(raw);
      for (const point of queue) {
        buffer.current = [...buffer.current, point];
        try { sendPosition(point.lat, point.lon, point.speed_kmh); } catch { /* skip */ }
      }
      await AsyncStorage.removeItem(OFFLINE_QUEUE_KEY);
    } catch {
      // storage error
    }
  }

  async function startTracking(): Promise<boolean> {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') return false;

    buffer.current = [];
    startTime.current = Date.now();
    setElapsedSeconds(0);
    setCurrentSpeed(0);
    setAvgMovingSpeed(0);
    setPointCount(0);

    await flushOfflineQueue();

    // Capture immediately, then every 60 s
    await capturePosition();
    captureInterval.current = setInterval(capturePosition, CAPTURE_INTERVAL_MS);

    // Seconds clock
    clockInterval.current = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime.current) / 1000));
    }, 1000);

    setTracking(true);
    return true;
  }

  function stopTracking(): RutaResult | null {
    if (captureInterval.current) clearInterval(captureInterval.current);
    if (clockInterval.current) clearInterval(clockInterval.current);
    captureInterval.current = null;
    clockInterval.current = null;
    setTracking(false);

    AsyncStorage.removeItem(OFFLINE_QUEUE_KEY).catch(() => {});

    const pts = buffer.current;
    if (pts.length < 2) return null;

    // Sort by timestamp in case offline points arrived out of order
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

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (captureInterval.current) clearInterval(captureInterval.current);
      if (clockInterval.current) clearInterval(clockInterval.current);
    };
  }, []);

  return {
    state: { tracking, elapsedSeconds, currentSpeed, avgMovingSpeed, pointCount } as RutaState,
    startTracking,
    stopTracking,
  };
}
