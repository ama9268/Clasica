import { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity,
  ActivityIndicator, Alert, ScrollView,
} from 'react-native';
import MapView, { Marker, Polyline } from 'react-native-maps';
import { Ionicons } from '@expo/vector-icons';
import { getEditions, registerEdition, uploadActivity, getStravaActivities, uploadStravaActivity } from '@/api/editions';
import { useTracking } from '@/hooks/useTracking';
import { useRuta } from '@/hooks/useRuta';
import { useAuth } from '@/context/AuthContext';
import type { Edition, ActivityUploadResult } from '@/types';

// ─── Helpers ────────────────────────────────────────────────────────────────

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Returns true if now >= start_time - 30 min */
function isWithinWindow(start_time: string): boolean {
  const [h, m] = start_time.split(':').map(Number);
  const now = new Date();
  const startMs = (h * 60 + m - 30) * 60 * 1000;
  const nowMs = (now.getHours() * 60 + now.getMinutes()) * 60 * 1000 + now.getSeconds() * 1000;
  return nowMs >= startMs;
}

function formatTime(s: string): string {
  return s.substring(0, 5); // "HH:MM"
}

function formatElapsed(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function routeCoords(edition: Edition & { route_geojson?: { coordinates: [number, number][] } | null }) {
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

// ─── Component ──────────────────────────────────────────────────────────────

type ScreenState =
  | 'loading'
  | 'no_edition'
  | 'too_early'
  | 'not_registered'
  | 'ready'
  | 'tracking'
  | 'uploading'      // buscando en Strava
  | 'uploading_gps'  // fallback GPS
  | 'done';

export default function RutaScreen() {
  const { user } = useAuth();
  const [screenState, setScreenState] = useState<ScreenState>('loading');
  const [edition, setEdition] = useState<any | null>(null);
  const [nextEdition, setNextEdition] = useState<Edition | null>(null);
  const [result, setResult] = useState<ActivityUploadResult | null>(null);
  const [registering, setRegistering] = useState(false);

  // WebSocket live tracking (other participants)
  const { positions, connected, sendPosition, disconnect } = useTracking(edition?.id ?? 0);

  // GPS ruta hook
  const { state: ruta, startTracking, stopTracking } = useRuta(sendPosition);

  // ── Load editions on mount ──
  const load = useCallback(async () => {
    setScreenState('loading');
    try {
      const editions = await getEditions();
      const today = todayISO();

      const todayOpen = editions.find(
        (e) => e.status === 'open' && e.date === today
      ) ?? null;

      if (!todayOpen) {
        const next = editions
          .filter((e) => e.status === 'open' && e.date > today)
          .sort((a, b) => a.date.localeCompare(b.date))[0] ?? null;
        setNextEdition(next);
        setScreenState('no_edition');
        return;
      }

      if (!isWithinWindow(todayOpen.start_time)) {
        setEdition(todayOpen);
        setScreenState('too_early');
        return;
      }

      setEdition(todayOpen);
      setScreenState(todayOpen.is_registration_open ? 'not_registered' : 'ready');

      // Fetch full detail to get route_geojson + registration status
      const { getEdition } = await import('@/api/editions');
      const detail = await getEdition(todayOpen.id);
      setEdition(detail);
      setScreenState(detail.user_registered ? 'ready' : 'not_registered');
    } catch {
      setScreenState('no_edition');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── Register ──
  async function handleRegister() {
    if (!edition) return;
    setRegistering(true);
    try {
      await registerEdition(edition.id);
      setEdition((e: any) => ({ ...e, user_registered: true }));
      setScreenState('ready');
    } catch {
      Alert.alert('Error', 'No se pudo completar la inscripción.');
    } finally {
      setRegistering(false);
    }
  }

  // ── Start route ──
  async function handleStart() {
    const ok = await startTracking();
    if (!ok) {
      Alert.alert('Permisos GPS', 'Activa la ubicación para poder registrar la ruta.');
      return;
    }
    setScreenState('tracking');
  }

  // ── Finish route ──
  async function handleStop() {
    const rutaResult = stopTracking();
    disconnect(); // cerrar WS inmediatamente
    if (!edition) return;

    // ── Flujo Strava primero ──────────────────────────────────────
    if (user?.strava_connected) {
      setScreenState('uploading'); // "Buscando en Strava…"
      try {
        const activities = await getStravaActivities(edition.id);
        if (activities.length > 0) {
          const latest = activities[0];
          const res = await uploadStravaActivity(edition.id, latest.id);
          setResult(res);
          setScreenState('done');
          return;
        }
        Alert.alert('Strava', 'No hay actividades Strava de hoy. Usando track GPS propio.');
      } catch (err: any) {
        Alert.alert('Strava error', err?.response?.data?.detail ?? err?.message ?? 'Error desconocido');
      }
    }

    // ── Fallback: track GPS propio ────────────────────────────────
    if (!rutaResult) {
      Alert.alert('Sin datos GPS', 'Inicia el track y espera al menos 10 s antes de finalizar.');
      setScreenState('ready');
      return;
    }
    setScreenState('uploading_gps');
    try {
      const res = await uploadActivity(edition.id, rutaResult);
      setResult(res);
      setScreenState('done');
    } catch (err: any) {
      Alert.alert('Error GPS', err?.response?.data?.detail ?? err?.message ?? 'No se pudo subir el track.');
      setScreenState('ready');
    }
  }

  // ── Render ──

  if (screenState === 'loading') {
    return (
      <View style={s.center}>
        <ActivityIndicator color="#8b1a1a" size="large" />
      </View>
    );
  }

  if (screenState === 'no_edition') {
    return (
      <View style={s.center}>
        <Ionicons name="bicycle-outline" size={56} color="#d1c9b8" />
        <Text style={s.emptyTitle}>Sin edición activa hoy</Text>
        {nextEdition ? (
          <Text style={s.emptySubtitle}>Próxima edición: {nextEdition.date}</Text>
        ) : (
          <Text style={s.emptySubtitle}>No hay ediciones programadas próximamente.</Text>
        )}
      </View>
    );
  }

  if (screenState === 'too_early') {
    return (
      <View style={s.center}>
        <Ionicons name="time-outline" size={56} color="#d1c9b8" />
        <Text style={s.emptyTitle}>Todavía no es la hora</Text>
        <Text style={s.emptySubtitle}>
          La edición comienza a las {formatTime(edition.start_time)}.
        </Text>
        <Text style={s.emptySubtitle}>Podrás iniciar 30 minutos antes.</Text>
      </View>
    );
  }

  if (screenState === 'not_registered') {
    return (
      <ScrollView style={s.container} contentContainerStyle={s.notRegisteredContent}>
        <View style={s.banner}>
          <Text style={s.bannerDate}>{edition.date}</Text>
          <Text style={s.bannerName}>{edition.name}</Text>
          {edition.route_distance_km && (
            <View style={s.metaRow}>
              <Ionicons name="navigate-outline" size={14} color="#9ca3af" />
              <Text style={s.metaText}>{edition.route_distance_km.toFixed(1)} km</Text>
            </View>
          )}
        </View>
        <View style={s.actions}>
          <Text style={s.notRegisteredMsg}>No estás inscrito en esta edición.</Text>
          <TouchableOpacity style={s.primaryBtn} onPress={handleRegister} disabled={registering}>
            {registering
              ? <ActivityIndicator color="#f5f0e8" />
              : <Text style={s.primaryBtnText}>INSCRIBIRME</Text>}
          </TouchableOpacity>
        </View>
      </ScrollView>
    );
  }

  if (screenState === 'done' && result) {
    return (
      <ScrollView style={s.container} contentContainerStyle={s.doneContent}>
        <View style={s.banner}>
          <Text style={s.bannerDate}>{edition?.date}</Text>
          <Text style={s.bannerName}>Ruta completada</Text>
        </View>
        <View style={s.resultCard}>
          <Ionicons
            name={result.is_valid ? 'checkmark-circle' : 'close-circle'}
            size={48}
            color={result.is_valid ? '#15803d' : '#8b1a1a'}
          />
          <Text style={[s.validLabel, { color: result.is_valid ? '#15803d' : '#8b1a1a' }]}>
            {result.is_valid ? 'Track válido ✓' : 'Track no válido'}
          </Text>
          <View style={s.resultRow}>
            <Text style={s.resultLabel}>Tiempo</Text>
            <Text style={s.resultValue}>{result.elapsed_formatted}</Text>
          </View>
          {result.average_moving_speed != null && (
            <View style={s.resultRow}>
              <Text style={s.resultLabel}>Vel. media en movimiento</Text>
              <Text style={s.resultValue}>{result.average_moving_speed.toFixed(1)} km/h</Text>
            </View>
          )}
          <View style={s.resultRow}>
            <Text style={s.resultLabel}>Puntuación validación</Text>
            <Text style={s.resultValue}>{(result.validation_score * 100).toFixed(0)}%</Text>
          </View>
        </View>
        <TouchableOpacity style={s.secondaryBtn} onPress={load}>
          <Text style={s.secondaryBtnText}>VOLVER AL INICIO</Text>
        </TouchableOpacity>
      </ScrollView>
    );
  }

  if (screenState === 'uploading' || screenState === 'uploading_gps') {
    return (
      <View style={s.center}>
        <ActivityIndicator color="#8b1a1a" size="large" />
        <Text style={s.uploadingText}>
          {screenState === 'uploading'
            ? 'Buscando actividad en Strava…'
            : 'Subiendo track GPS al servidor…'}
        </Text>
      </View>
    );
  }

  // ── 'ready' | 'tracking' ─────────────────────────────────────────────────
  const coords = routeCoords(edition);
  const region = mapRegion(coords);

  return (
    <View style={s.mapContainer}>
      {/* Map */}
      <MapView style={s.map} region={region ?? undefined} showsUserLocation>
        {/* Official route */}
        {coords.length > 0 && (
          <Polyline coordinates={coords} strokeColor="#1a2744" strokeWidth={3} />
        )}
        {/* Other participants */}
        {Array.from(positions.values()).map((p) => (
          <Marker
            key={p.user_id}
            coordinate={{ latitude: p.lat, longitude: p.lng }}
            anchor={{ x: 0.5, y: 0.5 }}
          >
            <View style={s.otherMarker}>
              <Text style={s.otherMarkerText}>{p.username[0]?.toUpperCase()}</Text>
            </View>
          </Marker>
        ))}
      </MapView>

      {/* Status bar */}
      <View style={s.statusBar}>
        <View style={[s.dot, { backgroundColor: connected ? '#22c55e' : '#ef4444' }]} />
        <Text style={s.statusText}>
          {connected ? `${positions.size} en ruta` : 'Sin conexión'}
        </Text>
        <Text style={s.editionChip}>{edition?.name}</Text>
      </View>

      {/* Metrics panel (only while tracking) */}
      {screenState === 'tracking' && (
        <View style={s.metrics}>
          <View style={s.metricItem}>
            <Text style={s.metricValue}>{formatElapsed(ruta.elapsedSeconds)}</Text>
            <Text style={s.metricLabel}>TIEMPO</Text>
          </View>
          <View style={s.metricDivider} />
          <View style={s.metricItem}>
            <Text style={s.metricValue}>{ruta.currentSpeed.toFixed(1)}</Text>
            <Text style={s.metricLabel}>KM/H ACTUAL</Text>
          </View>
          <View style={s.metricDivider} />
          <View style={s.metricItem}>
            <Text style={s.metricValue}>{ruta.avgMovingSpeed.toFixed(1)}</Text>
            <Text style={s.metricLabel}>KM/H MEDIA</Text>
          </View>
          <View style={s.metricDivider} />
          <View style={s.metricItem}>
            <Text style={s.metricValue}>{ruta.pointCount}</Text>
            <Text style={s.metricLabel}>PUNTOS GPS</Text>
          </View>
        </View>
      )}

      {/* Action button */}
      <View style={s.actionBar}>
        {screenState === 'ready' && (
          <TouchableOpacity style={s.startBtn} onPress={handleStart}>
            <Ionicons name="play" size={20} color="#f5f0e8" />
            <Text style={s.startBtnText}>INICIAR RUTA</Text>
          </TouchableOpacity>
        )}
        {screenState === 'tracking' && (
          <TouchableOpacity style={s.stopBtn} onPress={handleStop}>
            <Ionicons name="stop" size={20} color="#f5f0e8" />
            <Text style={s.stopBtnText}>FINALIZAR RUTA</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

// ─── Styles ─────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f0e8' },
  notRegisteredContent: { flexGrow: 1 },
  doneContent: { flexGrow: 1, paddingBottom: 32 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f0e8', padding: 32 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: '#1a2744', marginTop: 16, textAlign: 'center' },
  emptySubtitle: { fontSize: 14, color: '#6b7280', marginTop: 8, textAlign: 'center' },
  banner: { backgroundColor: '#1a2744', padding: 24 },
  bannerDate: { fontSize: 11, color: '#9ca3af', letterSpacing: 2, marginBottom: 4 },
  bannerName: { fontSize: 20, fontWeight: '800', color: '#f5f0e8' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 },
  metaText: { fontSize: 13, color: '#9ca3af' },
  actions: { padding: 24, gap: 16 },
  notRegisteredMsg: { fontSize: 14, color: '#6b7280', textAlign: 'center' },
  primaryBtn: { backgroundColor: '#8b1a1a', paddingVertical: 14, alignItems: 'center' },
  primaryBtnText: { color: '#f5f0e8', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  secondaryBtn: {
    marginHorizontal: 24, marginTop: 16, borderWidth: 1, borderColor: '#8b1a1a',
    paddingVertical: 12, alignItems: 'center',
  },
  secondaryBtnText: { color: '#8b1a1a', fontSize: 13, fontWeight: '700', letterSpacing: 1 },
  uploadingText: { marginTop: 16, color: '#6b7280', fontSize: 14 },

  // Map layout
  mapContainer: { flex: 1 },
  map: { flex: 1 },

  // Status bar (top overlay)
  statusBar: {
    position: 'absolute', top: 0, left: 0, right: 0,
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: 'rgba(26,39,68,0.88)', paddingHorizontal: 16, paddingVertical: 10,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: 12, color: '#f5f0e8', flex: 1 },
  editionChip: { fontSize: 11, color: '#9ca3af', fontWeight: '600' },

  // Participant markers
  otherMarker: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: '#1a2744', justifyContent: 'center', alignItems: 'center',
    borderWidth: 2, borderColor: '#f5f0e8',
  },
  otherMarkerText: { color: '#f5f0e8', fontSize: 12, fontWeight: '700' },

  // Metrics panel
  metrics: {
    position: 'absolute', bottom: 80, left: 0, right: 0,
    flexDirection: 'row', backgroundColor: 'rgba(26,39,68,0.92)',
    paddingVertical: 12,
  },
  metricItem: { flex: 1, alignItems: 'center' },
  metricValue: { fontSize: 18, fontWeight: '800', color: '#f5f0e8' },
  metricLabel: { fontSize: 9, color: '#9ca3af', letterSpacing: 1, marginTop: 2 },
  metricDivider: { width: 1, backgroundColor: '#374151', marginVertical: 4 },

  // Action bar (bottom)
  actionBar: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    padding: 16, backgroundColor: '#f5f0e8',
  },
  startBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, backgroundColor: '#1a2744', paddingVertical: 16,
  },
  startBtnText: { color: '#f5f0e8', fontSize: 14, fontWeight: '700', letterSpacing: 2 },
  stopBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, backgroundColor: '#8b1a1a', paddingVertical: 16,
  },
  stopBtnText: { color: '#f5f0e8', fontSize: 14, fontWeight: '700', letterSpacing: 2 },

  // Done/result card
  resultCard: {
    margin: 24, backgroundColor: '#fff', padding: 24,
    alignItems: 'center', gap: 16,
  },
  validLabel: { fontSize: 16, fontWeight: '700' },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between', width: '100%' },
  resultLabel: { fontSize: 14, color: '#6b7280' },
  resultValue: { fontSize: 14, fontWeight: '700', color: '#1a2744' },
});
