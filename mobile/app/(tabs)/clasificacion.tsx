import { useEffect, useState } from 'react';
import {
  View, Text, FlatList, StyleSheet, ActivityIndicator, RefreshControl,
} from 'react-native';
import { getGeneralClassification } from '@/api/classifications';
import type { Classification } from '@/types';

const CATEGORY_COLOR: Record<string, string> = {
  open: '#1a2744',
  M40: '#7c3aed',
  M50: '#0369a1',
  M60: '#b45309',
};

const MEDAL: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };

export default function ClasificacionScreen() {
  const [data, setData] = useState<Classification[]>([]);
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
      keyExtractor={(_, i) => String(i)}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
      }
      ListHeaderComponent={
        <View style={s.headerRow}>
          <Text style={[s.col, { flex: 0.5 }]}>POS</Text>
          <Text style={[s.col, { flex: 2 }]}>CICLISTA</Text>
          <Text style={[s.col, { flex: 1, textAlign: 'right' }]}>TIEMPO</Text>
          <Text style={[s.col, { flex: 0.7, textAlign: 'right' }]}>CAT</Text>
        </View>
      }
      ListEmptyComponent={
        <Text style={s.empty}>No hay resultados publicados aún.</Text>
      }
      renderItem={({ item }) => (
        <View style={s.row}>
          <Text style={[s.pos, { flex: 0.5 }]}>
            {MEDAL[item.position_overall] ?? `${item.position_overall}º`}
          </Text>
          <View style={{ flex: 2 }}>
            <Text style={s.name}>{item.full_name}</Text>
            {item.club ? <Text style={s.club}>{item.club}</Text> : null}
          </View>
          <Text style={[s.time, { flex: 1 }]}>{item.time_formatted}</Text>
          <View style={[s.catBadge, { backgroundColor: CATEGORY_COLOR[item.category] ?? '#6b7280' }]}>
            <Text style={s.catText}>{item.category.toUpperCase()}</Text>
          </View>
        </View>
      )}
    />
  );
}

const s = StyleSheet.create({
  list: { flex: 1, backgroundColor: '#f5f0e8' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f0e8' },
  empty: { textAlign: 'center', color: '#6b7280', marginTop: 48, fontSize: 14 },
  headerRow: {
    flexDirection: 'row', backgroundColor: '#1a2744', paddingHorizontal: 16,
    paddingVertical: 10, alignItems: 'center',
  },
  col: { fontSize: 10, fontWeight: '700', color: '#f5f0e8', letterSpacing: 1 },
  row: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff',
    marginHorizontal: 0, paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#f3f4f6',
  },
  pos: { fontSize: 16, fontWeight: '800', color: '#1a2744' },
  name: { fontSize: 14, fontWeight: '600', color: '#1a1a1a' },
  club: { fontSize: 11, color: '#6b7280', marginTop: 1 },
  time: { fontSize: 13, fontWeight: '700', color: '#8b1a1a', textAlign: 'right', marginRight: 8 },
  catBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 2 },
  catText: { fontSize: 10, fontWeight: '700', color: '#fff' },
});
