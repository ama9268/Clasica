import { useEffect, useState } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { getEditions } from '@/api/editions';
import type { Edition } from '@/types';

const STATUS_LABEL: Record<Edition['status'], string> = {
  open: 'ABIERTA',
  closed: 'CERRADA',
  results_published: 'RESULTADOS',
};

const STATUS_COLOR: Record<Edition['status'], string> = {
  open: '#15803d',
  closed: '#6b7280',
  results_published: '#8b1a1a',
};

export default function EditionsScreen() {
  const router = useRouter();
  const [editions, setEditions] = useState<Edition[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      setEditions(await getEditions());
    } catch {
      // silencioso, lista vacía
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator color="#8b1a1a" size="large" />
      </View>
    );
  }

  return (
    <FlatList
      style={s.list}
      data={editions}
      keyExtractor={(e) => String(e.id)}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
      }
      ListEmptyComponent={
        <Text style={s.empty}>No hay ediciones disponibles.</Text>
      }
      renderItem={({ item }) => (
        <TouchableOpacity
          style={s.card}
          onPress={() => router.push(`/editions/${item.id}`)}
        >
          <View style={s.cardTop}>
            <Text style={s.date}>{item.date}</Text>
            <Text style={[s.status, { color: STATUS_COLOR[item.status] }]}>
              {STATUS_LABEL[item.status]}
            </Text>
          </View>
          <Text style={s.name}>{item.name}</Text>
          <View style={s.meta}>
            {item.route_distance_km && (
              <View style={s.chip}>
                <Ionicons name="navigate-outline" size={12} color="#6b7280" />
                <Text style={s.chipText}>{item.route_distance_km.toFixed(1)} km</Text>
              </View>
            )}
            {item.is_registration_open && (
              <View style={[s.chip, s.chipOpen]}>
                <Text style={[s.chipText, { color: '#15803d' }]}>Inscripción abierta</Text>
              </View>
            )}
          </View>
          <Ionicons name="chevron-forward" size={16} color="#9ca3af" style={s.chevron} />
        </TouchableOpacity>
      )}
    />
  );
}

const s = StyleSheet.create({
  list: { flex: 1, backgroundColor: '#f5f0e8' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f0e8' },
  empty: { textAlign: 'center', color: '#6b7280', marginTop: 48, fontSize: 14 },
  card: {
    backgroundColor: '#fff', marginHorizontal: 16, marginTop: 12,
    padding: 16, borderLeftWidth: 3, borderLeftColor: '#8b1a1a',
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2,
  },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  date: { fontSize: 11, color: '#6b7280', letterSpacing: 1, fontWeight: '600' },
  status: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  name: { fontSize: 17, fontWeight: '700', color: '#1a2744', marginBottom: 8 },
  meta: { flexDirection: 'row', gap: 8 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#f3f4f6', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 2 },
  chipOpen: { backgroundColor: '#dcfce7' },
  chipText: { fontSize: 11, color: '#6b7280' },
  chevron: { position: 'absolute', right: 16, top: '50%' },
});
