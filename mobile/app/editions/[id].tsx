import { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, Alert, Image,
} from 'react-native';
import MapView, { Polyline } from 'react-native-maps';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { getEdition, registerEdition } from '@/api/editions';
import type { EditionDetail, Classification, EditionMedia } from '@/types';
import { WindOverlay } from '@/components/WindOverlay';
import { ElevationChart } from '@/components/ElevationChart';

const MEDAL: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };

const SKY_ICON: Record<string, string> = {
  'despejado': 'sunny-outline',
  'nuboso': 'cloudy-outline',
  'cubierto': 'cloud-outline',
  'lluvia': 'rainy-outline',
  'tormenta': 'thunderstorm-outline',
};

function skyIcon(estado: string | null): string {
  if (!estado) return 'partly-sunny-outline';
  const key = Object.keys(SKY_ICON).find((k) => estado.toLowerCase().includes(k));
  return key ? SKY_ICON[key] : 'partly-sunny-outline';
}

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
  const isOpen = edition.status === 'open';
  const isClosed = edition.status === 'closed' || edition.status === 'results_published';
  const showWind = isOpen && !!edition.weather?.viento_dir;

  return (
    <ScrollView style={s.container}>
      {/* ── BANNER ── */}
      <View style={s.banner}>
        <Text style={s.date}>{edition.date}</Text>
        <Text style={s.name}>{edition.name}</Text>
        <View style={s.metaRow}>
          {edition.route_distance_km ? (
            <View style={s.metaItem}>
              <Ionicons name="navigate-outline" size={13} color="#9ca3af" />
              <Text style={s.metaText}>{edition.route_distance_km.toFixed(1)} km</Text>
            </View>
          ) : null}
          <View style={[s.statusBadge,
            isOpen ? s.statusOpen : isClosed && edition.status === 'results_published' ? s.statusPublished : s.statusClosed
          ]}>
            <Text style={s.statusText}>
              {isOpen ? 'ABIERTA' : edition.status === 'closed' ? 'CERRADA' : 'RESULTADOS'}
            </Text>
          </View>
        </View>
      </View>

      {/* ── MAPA ── */}
      {coords.length > 0 && region && (
        <View style={s.mapContainer}>
          <MapView style={s.map} region={region} scrollEnabled={false}>
            <Polyline coordinates={coords} strokeColor="#8b1a1a" strokeWidth={3} />
          </MapView>
          {showWind && (
            <WindOverlay
              direction={edition.weather!.viento_dir!}
              speed={edition.weather!.viento_vel || 5}
              height={220}
            />
          )}
        </View>
      )}

      {/* ── TARJETA METEOROLÓGICA (solo OPEN) ── */}
      {isOpen && edition.weather && (
        <View style={s.weatherCard}>
          <View style={s.weatherHeader}>
            <Ionicons name={skyIcon(edition.weather.estado_cielo) as any} size={20} color="#1a2744" />
            <Text style={s.weatherTitle}>
              {edition.weather.estado_cielo ?? 'Previsión meteorológica'}
            </Text>
          </View>
          <View style={s.weatherGrid}>
            {edition.weather.temperatura !== null && (
              <View style={s.weatherCell}>
                <Ionicons name="thermometer-outline" size={16} color="#8b1a1a" />
                <Text style={s.weatherValue}>{edition.weather.temperatura}°C</Text>
                <Text style={s.weatherKey}>Temperatura</Text>
              </View>
            )}
            {edition.weather.viento_vel !== null && (
              <View style={s.weatherCell}>
                <Ionicons name="flag-outline" size={16} color="#8b1a1a" />
                <Text style={s.weatherValue}>
                  {edition.weather.viento_vel} km/h{edition.weather.viento_dir ? ` ${edition.weather.viento_dir}` : ''}
                </Text>
                <Text style={s.weatherKey}>Viento</Text>
              </View>
            )}
            {edition.weather.lluvia !== null && (
              <View style={s.weatherCell}>
                <Ionicons name="water-outline" size={16} color="#8b1a1a" />
                <Text style={s.weatherValue}>{edition.weather.lluvia}%</Text>
                <Text style={s.weatherKey}>Lluvia</Text>
              </View>
            )}
          </View>
        </View>
      )}

      {/* ── PERFIL DE ELEVACIÓN ── */}
      {edition.elevation_profile && edition.elevation_profile.length > 1 && (
        <ElevationChart data={edition.elevation_profile} height={100} />
      )}

      {/* ══ BLOQUE OPEN ══ */}
      {isOpen && (
        <>
          {/* Acciones de inscripción */}
          <View style={s.actions}>
            {!edition.user_registered && (
              <TouchableOpacity style={s.primaryBtn} onPress={handleRegister} disabled={registering}>
                {registering
                  ? <ActivityIndicator color="#f5f0e8" />
                  : <Text style={s.primaryBtnText}>INSCRIBIRME</Text>
                }
              </TouchableOpacity>
            )}
            {edition.user_registered && (
              <View style={s.registeredBadge}>
                <Ionicons name="checkmark-circle" size={18} color="#15803d" />
                <Text style={s.registeredText}>Ya estás inscrito</Text>
              </View>
            )}
            {edition.is_live && (
              <TouchableOpacity
                style={s.liveBtn}
                onPress={() => router.push(`/live/${edition.id}`)}
              >
                <Ionicons name="radio-outline" size={16} color="#f5f0e8" />
                <Text style={s.liveBtnText}>VER EN VIVO</Text>
              </TouchableOpacity>
            )}
          </View>

          {/* Lista de inscritos */}
          {edition.participants_count > 0 && (
            <View style={s.section}>
              <Text style={s.sectionTitle}>INSCRITOS ({edition.participants_count})</Text>
              {edition.participants.map((p, i) => (
                <View key={i} style={s.participantRow}>
                  <Ionicons name="person-outline" size={14} color="#6b7280" />
                  <Text style={s.participantName}>{p.user__full_name || '—'}</Text>
                  {p.user__club ? <Text style={s.participantClub}>{p.user__club}</Text> : null}
                </View>
              ))}
            </View>
          )}
        </>
      )}

      {/* ══ BLOQUE CERRADA / RESULTADOS ══ */}
      {isClosed && (
        <>
          {/* Clasificación */}
          {edition.classifications.length > 0 && (
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

          {/* Galería media */}
          {edition.media.length > 0 && (
            <View style={s.section}>
              <Text style={s.sectionTitle}>GALERÍA</Text>
              <View style={s.mediaGrid}>
                {edition.media.map((m: EditionMedia) => (
                  <View key={m.id} style={s.mediaCard}>
                    {m.media_type === 'photo' && m.photo ? (
                      <Image source={{ uri: m.photo }} style={s.mediaImage} resizeMode="cover" />
                    ) : (
                      <View style={s.videoCard}>
                        <Ionicons name="play-circle-outline" size={32} color="#f5f0e8" />
                      </View>
                    )}
                    {m.caption ? <Text style={s.mediaCaption} numberOfLines={1}>{m.caption}</Text> : null}
                  </View>
                ))}
              </View>
            </View>
          )}
        </>
      )}

      <View style={{ height: 32 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f0e8' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f0e8' },

  // Banner
  banner: { backgroundColor: '#1a2744', padding: 24, paddingBottom: 20 },
  date: { fontSize: 11, color: '#9ca3af', letterSpacing: 2, marginBottom: 4 },
  name: { fontSize: 22, fontWeight: '800', color: '#f5f0e8', marginBottom: 10 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { fontSize: 13, color: '#9ca3af' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 3 },
  statusOpen: { backgroundColor: '#dcfce7' },
  statusClosed: { backgroundColor: '#fee2e2' },
  statusPublished: { backgroundColor: '#dbeafe' },
  statusText: { fontSize: 9, fontWeight: '800', color: '#111827' },

  // Mapa
  mapContainer: { position: 'relative' },
  map: { height: 220 },

  // Tarjeta meteo
  weatherCard: { backgroundColor: '#fff', margin: 16, marginBottom: 0, padding: 16, borderRadius: 8, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 3 },
  weatherHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  weatherTitle: { fontSize: 13, fontWeight: '700', color: '#1a2744', flex: 1 },
  weatherGrid: { flexDirection: 'row', justifyContent: 'space-around' },
  weatherCell: { alignItems: 'center', gap: 4 },
  weatherValue: { fontSize: 14, fontWeight: '700', color: '#1a1a1a' },
  weatherKey: { fontSize: 10, color: '#6b7280' },

  // Acciones
  actions: { padding: 16, gap: 10 },
  primaryBtn: { backgroundColor: '#8b1a1a', paddingVertical: 14, alignItems: 'center' },
  primaryBtnText: { color: '#f5f0e8', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  registeredBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#dcfce7', padding: 12, justifyContent: 'center' },
  registeredText: { color: '#15803d', fontSize: 13, fontWeight: '600' },
  liveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#8b1a1a', paddingVertical: 14 },
  liveBtnText: { color: '#f5f0e8', fontSize: 13, fontWeight: '700', letterSpacing: 2 },

  // Secciones genéricas
  section: { marginTop: 16 },
  sectionTitle: { fontSize: 10, fontWeight: '700', color: '#6b7280', letterSpacing: 2, paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#f5f0e8' },

  // Inscritos
  participantRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#fff', paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f3f4f6' },
  participantName: { fontSize: 14, color: '#1a1a1a', flex: 1 },
  participantClub: { fontSize: 11, color: '#6b7280' },

  // Clasificación
  classRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#f3f4f6' },
  classPos: { fontSize: 18, fontWeight: '800', color: '#1a2744', width: 36 },
  className: { fontSize: 14, fontWeight: '600', color: '#1a1a1a' },
  classClub: { fontSize: 11, color: '#6b7280' },
  classTime: { fontSize: 13, fontWeight: '700', color: '#8b1a1a' },

  // Media
  mediaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 2, paddingHorizontal: 16 },
  mediaCard: { width: '48.5%', backgroundColor: '#fff' },
  mediaImage: { width: '100%', height: 120 },
  videoCard: { width: '100%', height: 120, backgroundColor: '#1a2744', justifyContent: 'center', alignItems: 'center' },
  mediaCaption: { fontSize: 10, color: '#6b7280', padding: 6 },
});
