import { useState, useCallback } from 'react';
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  ActivityIndicator, Alert, RefreshControl
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect, Redirect } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getEditions, deleteEdition } from '@/api/editions';
import { useAuth } from '@/context/AuthContext';
import type { Edition } from '@/types';

export default function AdminDashboard() {
  const { user } = useAuth();
  if (!user?.is_staff) return <Redirect href="/(tabs)" />;
  const [editions, setEditions] = useState<Edition[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const loadEditions = useCallback(async () => {
    try {
      const data = await getEditions();
      setEditions(data);
    } catch (error) {
      Alert.alert('Error', 'No se pudieron cargar las ediciones.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadEditions();
    }, [loadEditions])
  );

  async function handleDelete(id: number) {
    Alert.alert(
      'Eliminar edición',
      '¿Estás seguro de que quieres eliminar esta edición? Esta acción no se puede deshacer.',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Eliminar',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteEdition(id);
              setEditions(editions.filter(e => e.id !== id));
              Alert.alert('Éxito', 'Edición eliminada correctamente.');
            } catch (error: any) {
              const msg = error.response?.data?.detail || 'No se pudo eliminar la edición.';
              Alert.alert('Error', msg);
            }
          }
        }
      ]
    );
  }

  const renderItem = ({ item }: { item: Edition }) => (
    <View style={s.card}>
      <View style={s.cardHeader}>
        <View>
          <Text style={s.cardDate}>{item.date}</Text>
          <Text style={s.cardTitle}>{item.name}</Text>
        </View>
        <View style={[s.statusBadge, item.status === 'open' ? s.statusOpen : s.statusClosed]}>
          <Text style={s.statusText}>
            {item.status === 'open' ? 'ABIERTA' : item.status === 'closed' ? 'CERRADA' : 'PUBLICADA'}
          </Text>
        </View>
      </View>

      <View style={s.actions}>
        <TouchableOpacity
          style={s.actionBtn}
          onPress={() => router.push(`/admin/edition-form?id=${item.id}`)}
        >
          <Ionicons name="pencil" size={16} color="#1a2744" />
          <Text style={s.actionText}>EDITAR</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={s.actionBtn}
          onPress={() => router.push(`/admin/media-manager?id=${item.id}`)}
        >
          <Ionicons name="images" size={16} color="#1a2744" />
          <Text style={s.actionText}>MEDIA</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[s.actionBtn, s.deleteBtn]}
          onPress={() => handleDelete(item.id)}
        >
          <Ionicons name="trash" size={16} color="#8b1a1a" />
          <Text style={[s.actionText, s.deleteText]}>BORRAR</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  if (loading && !refreshing) {
    return (
      <View style={s.center}>
        <ActivityIndicator color="#8b1a1a" size="large" />
      </View>
    );
  }

  return (
    <View style={s.container}>
      <View style={[s.header, { paddingTop: insets.top + 12 }]}>
        <Text style={s.headerTitle}>GESTIÓN DE EDICIONES</Text>
        <TouchableOpacity
          style={s.createBtn}
          onPress={() => router.push('/admin/edition-form')}
        >
          <Ionicons name="add" size={20} color="#f5f0e8" />
          <Text style={s.createBtnText}>NUEVA</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={editions}
        renderItem={renderItem}
        keyExtractor={item => item.id.toString()}
        contentContainerStyle={s.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => {
            setRefreshing(true);
            loadEditions();
          }} colors={['#8b1a1a']} tintColor="#8b1a1a" />
        }
        ListEmptyComponent={
          <Text style={s.emptyText}>No hay ediciones registradas.</Text>
        }
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f0e8' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingBottom: 16,
    backgroundColor: '#1a2744',
  },
  headerTitle: { fontSize: 14, fontWeight: '800', color: '#f5f0e8', letterSpacing: 1 },
  createBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#8b1a1a',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4
  },
  createBtnText: { color: '#f5f0e8', fontSize: 12, fontWeight: '700', marginLeft: 4 },
  list: { padding: 16 },
  card: {
    backgroundColor: '#fff',
    marginBottom: 16,
    borderRadius: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
    overflow: 'hidden'
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6'
  },
  cardDate: { fontSize: 11, color: '#6b7280', letterSpacing: 1, marginBottom: 2 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: '#1a1a1a' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 4, height: 22 },
  statusOpen: { backgroundColor: '#dcfce7' },
  statusClosed: { backgroundColor: '#fee2e2' },
  statusText: { fontSize: 9, fontWeight: '800', color: '#111827' },
  actions: { flexDirection: 'row', padding: 8 },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8
  },
  actionText: { fontSize: 11, fontWeight: '700', color: '#1a2744' },
  deleteBtn: { borderLeftWidth: 1, borderLeftColor: '#f3f4f6' },
  deleteText: { color: '#8b1a1a' },
  emptyText: { textAlign: 'center', marginTop: 40, color: '#6b7280' },
});
