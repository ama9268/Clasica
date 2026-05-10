import { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Link } from 'expo-router';
import { useAuth } from '@/context/AuthContext';

export default function LoginScreen() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!username || !password) return;
    setLoading(true);
    try {
      await login(username, password);
    } catch (e: any) {
      if (e.response?.status === 401 || e.response?.status === 400) {
        Alert.alert('Error', 'Usuario o contraseña incorrectos.');
      } else if (e.code === 'ECONNABORTED' || !e.response) {
        Alert.alert('Sin conexión', 'No se puede conectar al servidor. Comprueba que la URL de la API es correcta y que el servidor está activo.');
      } else {
        Alert.alert('Error', `Error ${e.response?.status ?? 'desconocido'}.`);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={s.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={s.header}>
        <Text style={s.title}>LA CLÁSICA</Text>
        <Text style={s.subtitle}>PRUEBA CICLISTA SEMANAL</Text>
      </View>

      <View style={s.card}>
        <Text style={s.label}>USUARIO</Text>
        <TextInput
          style={s.input}
          value={username}
          onChangeText={setUsername}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="tu_usuario"
          placeholderTextColor="#9ca3af"
        />

        <Text style={s.label}>CONTRASEÑA</Text>
        <TextInput
          style={s.input}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder="••••••••"
          placeholderTextColor="#9ca3af"
        />

        <TouchableOpacity style={s.btn} onPress={handleLogin} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#f5f0e8" />
          ) : (
            <Text style={s.btnText}>ENTRAR</Text>
          )}
        </TouchableOpacity>

        <Link href="/(auth)/register" asChild>
          <TouchableOpacity style={s.link}>
            <Text style={s.linkText}>¿No tienes cuenta? Regístrate</Text>
          </TouchableOpacity>
        </Link>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#1a2744', justifyContent: 'center', padding: 24 },
  header: { alignItems: 'center', marginBottom: 40 },
  title: { fontSize: 32, fontWeight: '800', color: '#f5f0e8', letterSpacing: 4 },
  subtitle: { fontSize: 11, color: '#8b1a1a', letterSpacing: 3, marginTop: 4 },
  card: { backgroundColor: '#f5f0e8', borderRadius: 2, padding: 24 },
  label: { fontSize: 10, fontWeight: '700', color: '#6b7280', letterSpacing: 2, marginBottom: 6, marginTop: 16 },
  input: {
    borderWidth: 1, borderColor: '#d1d5db', backgroundColor: '#fff',
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: '#1a1a1a',
  },
  btn: {
    backgroundColor: '#8b1a1a', paddingVertical: 14, alignItems: 'center',
    marginTop: 24,
  },
  btnText: { color: '#f5f0e8', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  link: { alignItems: 'center', marginTop: 16 },
  linkText: { color: '#1a2744', fontSize: 13 },
});
