import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, KeyboardAvoidingView, Platform, Alert, ActivityIndicator,
} from 'react-native';
import { Link } from 'expo-router';
import { useAuth } from '@/context/AuthContext';

export default function RegisterScreen() {
  const { register } = useAuth();
  const [form, setForm] = useState({
    username: '', email: '', password: '',
    full_name: '', birth_date: '', club: '',
  });
  const [loading, setLoading] = useState(false);

  function set(key: string, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleRegister() {
    const { username, email, password, full_name, birth_date } = form;
    if (!username || !email || !password || !full_name || !birth_date) {
      Alert.alert('Error', 'Rellena todos los campos obligatorios.');
      return;
    }
    setLoading(true);
    try {
      await register(form);
    } catch (e: any) {
      const msg = e.response?.data
        ? JSON.stringify(e.response.data)
        : 'Error al registrarse.';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  }

  const fields: Array<{
    key: keyof typeof form; label: string; placeholder: string;
    secure?: boolean; keyboard?: 'email-address' | 'default';
  }> = [
    { key: 'full_name', label: 'NOMBRE COMPLETO *', placeholder: 'Antonio García' },
    { key: 'username', label: 'USUARIO *', placeholder: 'antonio_garcia' },
    { key: 'email', label: 'EMAIL *', placeholder: 'antonio@email.com', keyboard: 'email-address' },
    { key: 'password', label: 'CONTRASEÑA *', placeholder: '••••••••', secure: true },
    { key: 'birth_date', label: 'FECHA DE NACIMIENTO * (AAAA-MM-DD)', placeholder: '1980-03-15' },
    { key: 'club', label: 'CLUB', placeholder: 'C.C. Ejemplo' },
  ];

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
    <ScrollView style={s.container} contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
      <View style={s.header}>
        <Text style={s.title}>LA CLÁSICA</Text>
        <Text style={s.subtitle}>CREAR CUENTA</Text>
      </View>

      <View style={s.card}>
        {fields.map(({ key, label, placeholder, secure, keyboard }) => (
          <View key={key}>
            <Text style={s.label}>{label}</Text>
            <TextInput
              style={s.input}
              value={form[key]}
              onChangeText={(v) => set(key, v)}
              placeholder={placeholder}
              placeholderTextColor="#9ca3af"
              secureTextEntry={secure}
              keyboardType={keyboard ?? 'default'}
              autoCapitalize="none"
            />
          </View>
        ))}

        <TouchableOpacity style={s.btn} onPress={handleRegister} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#f5f0e8" />
          ) : (
            <Text style={s.btnText}>REGISTRARSE</Text>
          )}
        </TouchableOpacity>

        <Link href="/(auth)/login" asChild>
          <TouchableOpacity style={s.link}>
            <Text style={s.linkText}>¿Ya tienes cuenta? Inicia sesión</Text>
          </TouchableOpacity>
        </Link>
      </View>
    </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#1a2744' },
  content: { padding: 24, paddingBottom: 48 },
  header: { alignItems: 'center', marginBottom: 32, marginTop: 48 },
  title: { fontSize: 28, fontWeight: '800', color: '#f5f0e8', letterSpacing: 4 },
  subtitle: { fontSize: 11, color: '#8b1a1a', letterSpacing: 3, marginTop: 4 },
  card: { backgroundColor: '#f5f0e8', borderRadius: 2, padding: 24 },
  label: { fontSize: 10, fontWeight: '700', color: '#6b7280', letterSpacing: 2, marginBottom: 6, marginTop: 16 },
  input: {
    borderWidth: 1, borderColor: '#d1d5db', backgroundColor: '#fff',
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: '#1a1a1a',
  },
  btn: { backgroundColor: '#8b1a1a', paddingVertical: 14, alignItems: 'center', marginTop: 24 },
  btnText: { color: '#f5f0e8', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  link: { alignItems: 'center', marginTop: 16 },
  linkText: { color: '#1a2744', fontSize: 13 },
});
