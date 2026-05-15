import { useEffect, useState } from 'react';
import {
  View, Text, Image, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'expo-router';
import { getUserStats } from '@/api/classifications';
import { getStravaAuthUrl, disconnectStrava } from '@/api/auth';
import client from '@/api/client';
import type { UserStats } from '@/types';

export default function PerfilScreen() {
  const { user, logout, refreshUser } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [stravaLoading, setStravaLoading] = useState(false);

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

  async function handleStravaConnect() {
    try {
      setStravaLoading(true);
      // Strava solo acepta redirect URIs http/https, usamos el callback web del servidor.
      // El servidor guarda los tokens al completar el OAuth; el móvil solo refresca el perfil.
      console.log('API base:', client.defaults.baseURL);
      const { auth_url } = await getStravaAuthUrl('web');
      await WebBrowser.openBrowserAsync(auth_url);
      // Después de que el usuario cierra el navegador, refrescamos el perfil
      await refreshUser();
    } catch (err) {
      console.error('Strava connect error:', err);
      Alert.alert('Error', 'No se pudo conectar con Strava. Inténtalo de nuevo.');
    } finally {
      setStravaLoading(false);
    }
  }

  async function handleStravaDisconnect() {
    Alert.alert('Desconectar Strava', '¿Quieres desconectar tu cuenta de Strava?', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Desconectar',
        style: 'destructive',
        onPress: async () => {
          try {
            setStravaLoading(true);
            await disconnectStrava();
            await refreshUser();
          } catch {
            Alert.alert('Error', 'No se pudo desconectar Strava.');
          } finally {
            setStravaLoading(false);
          }
        },
      },
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

      {/* Bloque Strava */}
      <View style={s.stravaCard}>
        <Text style={s.sectionTitle}>STRAVA</Text>
        {user.strava_connected ? (
          <View style={s.stravaConnected}>
            <Ionicons name="checkmark-circle" size={18} color="#15803d" />
            <View style={{ flex: 1 }}>
              <Text style={s.stravaStatus}>Cuenta conectada</Text>
              <Text style={s.stravaId}>Athlete ID: {user.strava_athlete_id}</Text>
            </View>
            <TouchableOpacity onPress={handleStravaDisconnect} disabled={stravaLoading}>
              <Text style={s.stravaUnlink}>Desconectar</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity style={s.stravaBtn} onPress={handleStravaConnect} disabled={stravaLoading}>
            {stravaLoading
              ? <ActivityIndicator color="#fff" size="small" />
              : <Text style={s.stravaBtnText}>Conectar con Strava</Text>
            }
          </TouchableOpacity>
        )}
      </View>

      {user.is_staff && (
        <TouchableOpacity
          style={s.adminBtn}
          onPress={() => router.push('/admin')}
        >
          <Ionicons name="shield-checkmark-outline" size={18} color="#1a2744" />
          <Text style={s.adminText}>ADMINISTRACIÓN</Text>
        </TouchableOpacity>
      )}

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
  adminBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginHorizontal: 16, marginTop: 32, padding: 14, backgroundColor: '#f5f0e8', borderWidth: 1, borderColor: '#1a2744' },
  adminText: { fontSize: 13, fontWeight: '700', color: '#1a2744', letterSpacing: 1 },
  stravaCard: { marginHorizontal: 16, marginTop: 24, backgroundColor: '#fff', padding: 16 },
  stravaConnected: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  stravaStatus: { fontSize: 13, fontWeight: '600', color: '#15803d' },
  stravaId: { fontSize: 11, color: '#9ca3af', marginTop: 1 },
  stravaUnlink: { fontSize: 11, fontWeight: '700', color: '#8b1a1a', textDecorationLine: 'underline' },
  stravaBtn: { backgroundColor: '#FC4C02', alignItems: 'center', justifyContent: 'center', paddingVertical: 12, marginTop: 8 },
  stravaBtnText: { color: '#fff', fontSize: 13, fontWeight: '700', letterSpacing: 1 },
});
