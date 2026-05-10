import React, { createContext, useContext, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
} from '../api/auth';
import type { User } from '../types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (payload: {
    username: string;
    email: string;
    password: string;
    full_name: string;
    birth_date: string;
    club: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await SecureStore.getItemAsync('access_token');
      if (token) {
        try {
          setUser(await getMe());
        } catch {
          // token inválido, se ignorará y se redirigirá a login
        }
      }
      setLoading(false);
    })();
  }, []);

  async function login(username: string, password: string) {
    await apiLogin(username, password);
    setUser(await getMe());
  }

  async function register(payload: Parameters<typeof apiRegister>[0]) {
    await apiRegister(payload);
    setUser(await getMe());
  }

  async function logout() {
    await apiLogout();
    setUser(null);
  }

  async function refreshUser() {
    setUser(await getMe());
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
