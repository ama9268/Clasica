import { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, Alert,
} from 'react-native';
import MapView, { Polyline } from 'react-native-maps';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { getEdition, registerEdition } from '@/api/editions';
import type { EditionDetail, Classification } from '@/types';

const MEDAL: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };

function routeCoords(edition: EditionDetail) {
  if (!edition.route_geojson) return [];
  return edition.route_geojson.coordinates.map(([lng, lat]) => ({ latitude: lat, longitude: lng }));
}

function mapRegion(coords: { latitude: number; longitude: number }[]) {
  if (!coords.length) return undefined;
  const lats = coords.map((c) => c.latitude);
  const lngs = coords.map((c) => c.longitude);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  return {
    latitude: (minLat + maxLat) / 2,
    longitude: (minLng + maxLng) / 2,
    latitudeDelta: (maxLat - minLat) * 1.4 || 0.05,
    longitudeDelta: (maxLng - minLng) * 1.4 || 0.05,
  };
}

export default function EditionDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [edition, setEdition] = useState<EditionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    getEdition(Number(id))
      .then(setEdition)
      .catch(() => Alert.alert('Error', 'No se pudo cargar la edición.'))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleRegister() {
    if (!edition) return;
    setRegistering(true);
    try {
      await registerEdition(edition.id);
      setEdition((e) => e ? { ...e, user_registered: true } : e);
    } catch {
      Alert.alert('Error', 'No se pudo completar la inscripción.');
    } finally {
      setRegistering(false);
    }
  }

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator color="#8b1a1a" size="large" />
      </View>
    );
  }

  if (!edition) return null;

  const coords = routeCoords(edition);
  const region = mapRegion(coords);

  return (
    <ScrollView style={s.container}>
      <View style={s.banner}>
        <Text style={s.date}>{edition.date}</Text>
        <Text style={s.name}>{edition.name}</Text>
        {edition.route_distance_km && (
          <View style={s.metaRow}>
            <Ionicons name="navigate-outline" size={14} color="#9ca3af" />
            <Text style={s.metaText}>{edition.route_distance_km.toFixed(1)} km</Text>
          </View>
        )}
      </View>

      {coords.length > 0 && region && (
        <View style={s.mapContainer}>
          <MapView style={s.map} region={region} scrollEnabled={false}>
            <Polyline coordinates={coords} strokeColor="#8b1a1a" strokeWidth={3} />
          </MapView>
          {edition.weather && (
            <View style={s.weatherOverlay}>
              {edition.weather.temperatura !== null && (
                <View style={s.weatherItem}>
                  <Ionicons name="thermometer-outline" size={14} color="#1a2744" />
                  <Text style={s.weatherText}>{edition.weather.temperatura}°C</Text>
                </View>
              )}
              {edition.weather.viento_vel !== null && (
                <View style={s.weatherItem}>
                  <Ionicons name="flag-outline" size={14} color="#1a2744" />
                  <Text style={s.weatherText}>
                    {edition.weather.viento_vel} km/h {edition.weather.viento_dir ? `(${edition.weather.viento_dir})` : ''}
                  </Text>
                </View>
              )}
              {edition.weather.lluvia !== null && edition.weather.lluvia > 0 && (
                <View style={s.weatherItem}>
                  <Ionicons name="water-outline" size={14} color="#1a2744" />
                  <Text style={s.weatherText}>{edition.weather.lluvia}%</Text>
                </View>
              )}
            </View>
          )}
        </View>
      )}

      <View style={s.actions}>
        {edition.is_registration_open && !edition.user_registered && (
          <TouchableOpacity style={s.primaryBtn} onPress={handleRegister} disabled={registering}>
            {registering ? (
              <ActivityIndicator color="#f5f0e8" />
            ) : (
              <Text style={s.primaryBtnText}>INSCRIBIRME</Text>
            )}
          </TouchableOpacity>
        )}
        {edition.user_registered && (
          <View style={s.registeredBadge}>
            <Ionicons name="checkmark-circle" size={18} color="#15803d" />
            <Text style={s.registeredText}>Ya estás inscrito</Text>
          </View>
        )}
        {edition.status === 'open' && edition.user_registered && (
          <TouchableOpacity
            style={s.secondaryBtn}
            onPress={() => router.push(`/live/${edition.id}`)}
          >
            <Ionicons name="radio-outline" size={16} color="#8b1a1a" />
            <Text style={s.secondaryBtnText}>VER EN VIVO</Text>
          </TouchableOpacity>
        )}
      </View>

      {edition.results_published && edition.classifications.length > 0 && (
        <View style={s.section}>
          <Text style={s.sectionTitle}>CLASIFICACIÓN</Text>
          {edition.classifications.map((c: Classification) => (
            <View key={c.user_id} style={s.classRow}>
              <Text style={s.classPos}>
                {MEDAL[c.position_overall] ?? `${c.position_overall}º`}
              </Text>
              <View style={{ flex: 1 }}>
                <Text style={s.className}>{c.full_name}</Text>
                {c.club ? <Text style={s.classClub}>{c.club}</Text> : null}
              </View>
              <Text style={s.classTime}>{c.time_formatted}</Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f0e8' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f0e8' },
  banner: { backgroundColor: '#1a2744', padding: 24 },
  date: { fontSize: 11, color: '#9ca3af', letterSpacing: 2, marginBottom: 4 },
  name: { fontSize: 22, fontWeight: '800', color: '#f5f0e8' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 },
  metaText: { fontSize: 13, color: '#9ca3af' },
  mapContainer: { position: 'relative' },
  map: { height: 220, marginHorizontal: 0 },
  weatherOverlay: {
    position: 'absolute',
    top: 10,
    right: 10,
    backgroundColor: 'rgba(255, 255, 255, 0.9)',
    padding: 8,
    borderRadius: 8,
    gap: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 2,
    elevation: 3,
  },
  weatherItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  weatherText: { fontSize: 12, fontWeight: '600', color: '#1a2744' },
  actions: { padding: 16, gap: 10 },
  primaryBtn: { backgroundColor: '#8b1a1a', paddingVertical: 14, alignItems: 'center' },
  primaryBtnText: { color: '#f5f0e8', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  secondaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1, borderColor: '#8b1a1a', paddingVertical: 12 },
  secondaryBtnText: { color: '#8b1a1a', fontSize: 13, fontWeight: '700', letterSpacing: 1 },
  registeredBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#dcfce7', padding: 12, justifyContent: 'center' },
  registeredText: { color: '#15803d', fontSize: 13, fontWeight: '600' },
  section: { marginTop: 8, paddingBottom: 32 },
  sectionTitle: { fontSize: 11, fontWeight: '700', color: '#6b7280', letterSpacing: 2, paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#f5f0e8' },
  classRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#f3f4f6' },
  classPos: { fontSize: 18, fontWeight: '800', color: '#1a2744', width: 36 },
  className: { fontSize: 14, fontWeight: '600', color: '#1a1a1a' },
  classClub: { fontSize: 11, color: '#6b7280' },
  classTime: { fontSize: 13, fontWeight: '700', color: '#8b1a1a' },
});
