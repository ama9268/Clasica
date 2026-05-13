import { Redirect } from 'expo-router';
import { useAuth } from '@/context/AuthContext';

export default function PanelTab() {
  const { user } = useAuth();
  if (!user?.is_staff) return <Redirect href="/(tabs)" />;
  return <Redirect href="/admin" />;
}
