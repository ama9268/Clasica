import { Stack, useRouter, useSegments } from 'expo-router';
import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { AuthProvider, useAuth } from '@/context/AuthContext';
// Registra la tarea de localización en background antes de la navegación
import '@/tasks/locationTask';

function Guard() {
  const { user, loading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    const inAuth = segments[0] === '(auth)';
    if (!user && !inAuth) router.replace('/(auth)/login');
    else if (user && inAuth) router.replace('/(tabs)');
  }, [user, loading, segments]);

  if (loading) {
    return (
      <View
        style={{
          flex: 1,
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: '#1a2744',
        }}
      >
        <ActivityIndicator color="#f5f0e8" size="large" />
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: '#1a2744' },
        headerTintColor: '#f5f0e8',
        headerTitleStyle: { fontWeight: '700' },
        headerBackTitle: 'Volver',
      }}
    >
      <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="editions/[id]" options={{ title: 'Edición' }} />
      <Stack.Screen name="live/[id]" options={{ title: 'En Vivo' }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <Guard />
    </AuthProvider>
  );
}
