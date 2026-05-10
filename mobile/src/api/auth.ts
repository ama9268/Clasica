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
