import { useEffect, useState } from 'react';
import {
  View, Text, FlatList, StyleSheet, ActivityIndicator, RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { getGeneralClassification } from '@/api/classifications';
import type { GeneralRankingEntry } from '@/types';

const MEDAL: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };

export default function ClasificacionScreen() {
  const [data, setData] = useState<GeneralRankingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      setData(await getGeneralClassification());
    } catch {
      //
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
      data={data}
      keyExtractor={(item) => String(item.user__pk)}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => { setRefreshing(true); load(); }}
          colors={['#8b1a1a']}
          tintColor="#8b1a1a"
        />
      }
      ListHeaderComponent={
        <View style={s.headerRow}>
          <Text style={[s.col, { width: 36 }]}>#</Text>
          <Text style={[s.col, { flex: 1 }]}>CICLISTA</Text>
          <Text style={[s.col, s.colRight, { width: 44 }]}>✓</Text>
          <Text style={[s.col, s.colRight, { width: 44 }]}>TOTAL</Text>
        </View>
      }
      ListEmptyComponent={
        <View style={s.emptyContainer}>
          <Ionicons name="podium-outline" size={48} color="#d1d5db" />
          <Text style={s.empty}>No hay participantes registrados aún.</Text>
        </View>
      }
      renderItem={({ item, index }) => (
        <View style={[s.row, index === 0 && s.rowFirst]}>
          <Text style={[s.pos, { width: 36 }]}>
            {MEDAL[index + 1] ?? `${index + 1}º`}
          </Text>
          <View style={{ flex: 1 }}>
            <Text style={s.name}>{item['user__full_name'] || item['user__username']}</Text>
            {item['user__club'] ? (
              <Text style={s.club}>{item['user__club']}</Text>
            ) : null}
          </View>
          <View style={[s.badge, { width: 44 }]}>
            <Text style={s.badgeText}>{item.valid}</Text>
          </View>
          <Text style={[s.total, { width: 44 }]}>{item.total}</Text>
        </View>
      )}
    />
  );
}

const s = StyleSheet.create({
  list: { flex: 1, backgroundColor: '#f5f0e8' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f0e8' },
  emptyContainer: { alignItems: 'center', marginTop: 60, gap: 12 },
  empty: { textAlign: 'center', color: '#6b7280', fontSize: 14 },
  headerRow: {
    flexDirection: 'row', backgroundColor: '#1a2744',
    paddingHorizontal: 16, paddingVertical: 10, alignItems: 'center',
  },
  col: { fontSize: 10, fontWeight: '700', color: '#f5f0e8', letterSpacing: 1 },
  colRight: { textAlign: 'right' },
  row: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#f3f4f6',
  },
  rowFirst: { borderTopWidth: 2, borderTopColor: '#f59e0b' },
  pos: { fontSize: 16, fontWeight: '800', color: '#1a2744' },
  name: { fontSize: 14, fontWeight: '600', color: '#1a1a1a' },
  club: { fontSize: 11, color: '#6b7280', marginTop: 1 },
  badge: { backgroundColor: '#8b1a1a', borderRadius: 3, paddingVertical: 2, alignItems: 'center', marginRight: 4 },
  badgeText: { fontSize: 12, fontWeight: '700', color: '#fff' },
  total: { fontSize: 12, color: '#6b7280', textAlign: 'right' },
});
