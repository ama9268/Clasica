import * as SecureStore from 'expo-secure-store';
import client from './client';
import type { AuthTokens, User } from '../types';

export async function login(username: string, password: string): Promise<void> {
  const { data } = await client.post<AuthTokens>('/auth/login/', {
    username,
    password,
  });
  await SecureStore.setItemAsync('access_token', data.access);
  await SecureStore.setItemAsync('refresh_token', data.refresh);
}

export async function register(payload: {
  username: string;
  email: string;
  password: string;
  full_name: string;
  birth_date: string;
  club: string;
}): Promise<void> {
  await client.post('/auth/register/', payload);
  await login(payload.username, payload.password);
}

export async function getMe(): Promise<User> {
  const { data } = await client.get<User>('/auth/me/');
  return data;
}

export async function updateMe(payload: Partial<User>): Promise<User> {
  const { data } = await client.patch<User>('/auth/me/', payload);
  return data;
}

export async function logout(): Promise<void> {
  await SecureStore.deleteItemAsync('access_token');
  await SecureStore.deleteItemAsync('refresh_token');
}

export async function getStravaAuthUrl(redirectUri: string): Promise<{ auth_url: string; state: string }> {
  const { data } = await client.get<{ auth_url: string; state: string }>(
    `/auth/strava/auth-url/?redirect_uri=${encodeURIComponent(redirectUri)}`
  );
  return data;
}

export async function connectStrava(code: string, redirectUri: string, state: string): Promise<{ strava_athlete_id: number }> {
  const { data } = await client.post<{ strava_athlete_id: number }>('/auth/strava/connect/', {
    code,
    redirect_uri: redirectUri,
    state,
  });
  return data;
}

export async function disconnectStrava(): Promise<void> {
  await client.post('/auth/strava/disconnect/');
}
