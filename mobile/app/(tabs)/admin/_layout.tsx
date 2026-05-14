import { Stack } from 'expo-router';

export default function AdminLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: '#1a2744' },
        headerTintColor: '#f5f0e8',
        headerTitleStyle: { fontWeight: '700', letterSpacing: 2 },
        headerBackTitle: 'Volver',
      }}
    >
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="edition-form" options={{ title: 'EDICIÓN' }} />
      <Stack.Screen name="media-manager" options={{ title: 'GALERÍA' }} />
    </Stack>
  );
}
