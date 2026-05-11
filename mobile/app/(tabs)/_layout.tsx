import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

function icon(name: IoniconName) {
  return ({ color }: { color: string }) => (
    <Ionicons name={name} size={22} color={color} />
  );
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: '#8b1a1a',
        tabBarInactiveTintColor: '#9ca3af',
        tabBarStyle: { backgroundColor: '#fff', borderTopColor: '#e5e7eb' },
        headerStyle: { backgroundColor: '#1a2744' },
        headerTintColor: '#f5f0e8',
        headerTitleStyle: { fontWeight: '700', letterSpacing: 2 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: 'EDICIONES', tabBarIcon: icon('calendar-outline') }}
      />
      <Tabs.Screen
        name="clasificacion"
        options={{ title: 'CLASIFICACIÓN', tabBarIcon: icon('podium-outline') }}
      />
      <Tabs.Screen
        name="ruta"
        options={{ title: 'RUTA', tabBarIcon: icon('bicycle-outline') }}
      />
      <Tabs.Screen
        name="perfil"
        options={{ title: 'PERFIL', tabBarIcon: icon('person-outline') }}
      />
    </Tabs>
  );
}
