import * as TaskManager from 'expo-task-manager';
import * as Location from 'expo-location';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { RutaPoint } from '../types';

export const LOCATION_TASK = 'clasica-location';
export const BUFFER_KEY = '@clasica/location_buffer';

TaskManager.defineTask(
  LOCATION_TASK,
  async ({ data, error }: TaskManager.TaskManagerTaskBody<{ locations: Location.LocationObject[] }>) => {
    if (error) return;
    const { locations } = data;
    try {
      const raw = await AsyncStorage.getItem(BUFFER_KEY);
      const buf: RutaPoint[] = raw ? JSON.parse(raw) : [];
      for (const loc of locations) {
        buf.push({
          lon: loc.coords.longitude,
          lat: loc.coords.latitude,
          speed_kmh: Math.max(0, (loc.coords.speed ?? 0) * 3.6),
          timestamp: loc.timestamp,
        });
      }
      await AsyncStorage.setItem(BUFFER_KEY, JSON.stringify(buf));
    } catch {
      // error de storage — punto perdido
    }
  }
);
