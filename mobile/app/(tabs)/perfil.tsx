import { useEffect, useState } from 'react';
import {
  View, Text, Image, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '@/context/AuthContext';
import { getUserStats } from '@/api/classifications';
import type { UserStats } from '@/types';

export default function PerfilScreen() {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    getUserStats(user.id)
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user]);

  async function handleLogout() {
    Alert.alert('Cerrar sesión', '¿Seguro?', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Salir', style: 'destructive', onPress: logout },
    ]);
  }

  if (!user) return null;

  return (
    <ScrollView style={s.container}>
      <View style={s.banner}>
        {user.photo ? (
          <Image source={{ uri: user.photo }} style={s.avatar} />
        ) : (
          <View style={[s.avatar, s.avatarPlaceholder]}>
            <Ionicons name="person" size={40} color="#f5f0e8" />
          </View>
        )}
        <Text style={s.name}>{user.full_name}</Text>
        <Text style={s.username}>@{user.username}</Text>
        {user.club ? <Text style={s.club}>{user.club}</Text> : null}
      </View>

      {loading ? (
        <ActivityIndicator color="#8b1a1a" style={{ marginTop: 32 }} />
      ) : stats ? (
        <>
          <View style={s.statsRow}>
            <View style={s.stat}>
              <Text style={s.statNum}>{stats.total_participations}</Text>
              <Text style={s.statLabel}>SALIDAS</Text>
            </View>
            <View style={s.statDivider} />
            <View style={s.stat}>
              <Text style={s.statNum}>{stats.total_valid}</Text>
              <Text style={s.statLabel}>VÁLIDAS</Text>
            </View>
            <View style={s.statDivider} />
            <View style={s.stat}>
              <Text style={s.statNum}>
                {stats.total_participations > 0
                  ? Math.round((stats.total_valid / stats.total_participations) * 100)
                  : 0}%
              </Text>
              <Text style={s.statLabel}>EFECTIVIDAD</Text>
            </View>
          </View>

          <Text style={s.sectionTitle}>HISTORIAL</Text>
          {stats.participations.map((p, i) => (
            <View key={i} style={s.histRow}>
              <View style={{ flex: 1 }}>
                <Text style={s.histEdition}>{p.edition}</Text>
                {p.time_formatted && (
                  <Text style={s.histTime}>{p.time_formatted}</Text>
                )}
              </View>
              {p.position_overall ? (
                <Text style={s.histPos}>{p.position_overall}º</Text>
              ) : null}
              <Ionicons
                name={p.is_valid ? 'checkmark-circle' : 'close-circle'}
                size={20}
                color={p.is_valid ? '#15803d' : '#dc2626'}
                style={{ marginLeft: 8 }}
              />
            </View>
          ))}
        </>
      ) : null}

      <TouchableOpacity style={s.logoutBtn} onPress={handleLogout}>
        <Ionicons name="log-out-outline" size={18} color="#8b1a1a" />
        <Text style={s.logoutText}>CERRAR SESIÓN</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f0e8' },
  banner: { backgroundColor: '#1a2744', alignItems: 'center', paddingVertical: 32, paddingHorizontal: 24 },
  avatar: { width: 80, height: 80, borderRadius: 40, marginBottom: 12 },
  avatarPlaceholder: { backgroundColor: '#2d3a5e', justifyContent: 'center', alignItems: 'center' },
  name: { fontSize: 20, fontWeight: '800', color: '#f5f0e8' },
  username: { fontSize: 13, color: '#9ca3af', marginTop: 2 },
  club: { fontSize: 12, color: '#8b1a1a', marginTop: 4, letterSpacing: 1 },
  statsRow: { flexDirection: 'row', backgroundColor: '#fff', marginTop: 16, marginHorizontal: 16, padding: 20 },
  stat: { flex: 1, alignItems: 'center' },
  statNum: { fontSize: 24, fontWeight: '800', color: '#1a2744' },
  statLabel: { fontSize: 10, color: '#6b7280', letterSpacing: 1, marginTop: 2 },
  statDivider: { width: 1, backgroundColor: '#e5e7eb' },
  sectionTitle: { fontSize: 11, fontWeight: '700', color: '#6b7280', letterSpacing: 2, marginTop: 24, marginHorizontal: 16, marginBottom: 8 },
  histRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff',
    marginHorizontal: 16, marginBottom: 1, paddingHorizontal: 16, paddingVertical: 12,
  },
  histEdition: { fontSize: 13, fontWeight: '600', color: '#1a1a1a' },
  histTime: { fontSize: 12, color: '#8b1a1a', marginTop: 2 },
  histPos: { fontSize: 16, fontWeight: '700', color: '#1a2744' },
  logoutBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginHorizontal: 16, marginTop: 12, marginBottom: 40, padding: 14, borderWidth: 1, borderColor: '#8b1a1a' },
  logoutText: { fontSize: 13, fontWeight: '700', color: '#8b1a1a', letterSpacing: 1 },
});
