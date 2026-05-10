import { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import MapView, { Marker, Polyline, Region } from 'react-native-maps';
import * as Location from 'expo-location';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useTracking } from '@/hooks/useTracking';
import { getEdition } from '@/api/editions';
import { useAuth } from '@/context/AuthContext';
import type { EditionDetail } from '@/types';

export default function LiveTrackingScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const router = useRouter();
  const { positions, connected, sendPosition } = useTracking(Number(id));
  const [edition, setEdition] = useState<EditionDetail | null>(null);
  const [tracking, setTracking] = useState(false);
  const locationSub = useRef<Location.LocationSubscription | null>(null);
  const mapRef = useRef<MapView>(null);

  useEffect(() => {
    getEdition(Number(id)).then(setEdition).catch(() => {});
    return () => { locationSub.current?.remove(); };
  }, [id]);

  async function startTracking() {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permisos', 'Necesitamos acceso a tu ubicación para el tracking.');
      return;
    }
    setTracking(true);
    locationSub.current = await Location.watchPositionAsync(
      { accuracy: Location.Accuracy.High, timeInterval: 5000, distanceInterval: 10 },
      (loc) => {
        sendPosition(loc.coords.latitude, loc.coords.longitude, (loc.coords.speed ?? 0) * 3.6);
      }
    );
  }

  function stopTracking() {
    locationSub.current?.remove();
    locationSub.current = null;
    setTracking(false);
  }

  const routeCoords = edition?.route_geojson?.coordinates.map(([lng, lat]) => ({
    latitude: lat,
    longitude: lng,
  })) ?? [];

  const initialRegion: Region | undefined = routeCoords.length
    ? (() => {
        const lats = routeCoords.map((c) => c.latitude);
        const lngs = routeCoords.map((c) => c.longitude);
        return {
          latitude: (Math.min(...lats) + Math.max(...lats)) / 2,
          longitude: (Math.min(...lngs) + Math.max(...lngs)) / 2,
          latitudeDelta: (Math.max(...lats) - Math.min(...lats)) * 1.4 || 0.05,
          longitudeDelta: (Math.max(...lngs) - Math.min(...lngs)) * 1.4 || 0.05,
        };
      })()
    : undefined;

  const participantList = Array.from(positions.values());

  return (
    <View style={s.container}>
      <MapView ref={mapRef} style={s.map} initialRegion={initialRegion}>
        {routeCoords.length > 0 && (
          <Polyline coordinates={routeCoords} strokeColor="#8b1a1a" strokeWidth={3} />
        )}
        {participantList.map((p) => (
          <Marker
            key={p.user_id}
            coordinate={{ latitude: p.lat, longitude: p.lng }}
            title={p.username}
            description={`${p.speed.toFixed(0)} km/h`}
            pinColor={p.user_id === user?.id ? '#8b1a1a' : '#1a2744'}
          />
        ))}
      </MapView>

      <View style={s.statusBar}>
        <View style={[s.dot, { backgroundColor: connected ? '#15803d' : '#dc2626' }]} />
        <Text style={s.statusText}>
          {connected ? 'Conectado' : 'Desconectado'} · {participantList.length} en ruta
        </Text>
      </View>

      <View style={s.controls}>
        <TouchableOpacity style={s.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={20} color="#1a2744" />
        </TouchableOpacity>

        {!tracking ? (
          <TouchableOpacity style={s.trackBtn} onPress={startTracking}>
            <Ionicons name="navigate" size={18} color="#f5f0e8" />
            <Text style={s.trackBtnText}>INICIAR TRACKING</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={[s.trackBtn, s.trackBtnStop]} onPress={stopTracking}>
            <Ionicons name="stop" size={18} color="#f5f0e8" />
            <Text style={s.trackBtnText}>DETENER</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  map: { flex: 1 },
  statusBar: {
    position: 'absolute', top: 0, left: 0, right: 0,
    backgroundColor: 'rgba(26,39,68,0.9)', flexDirection: 'row',
    alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 8,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { color: '#f5f0e8', fontSize: 12, fontWeight: '600' },
  controls: {
    position: 'absolute', bottom: 32, left: 16, right: 16,
    flexDirection: 'row', gap: 12, alignItems: 'center',
  },
  backBtn: {
    backgroundColor: '#fff', width: 44, height: 44, borderRadius: 22,
    justifyContent: 'center', alignItems: 'center',
    shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 4, elevation: 3,
  },
  trackBtn: {
    flex: 1, backgroundColor: '#8b1a1a', flexDirection: 'row',
    alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 14,
    shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 4, elevation: 3,
  },
  trackBtnStop: { backgroundColor: '#374151' },
  trackBtnText: { color: '#f5f0e8', fontSize: 13, fontWeight: '700', letterSpacing: 1 },
});
