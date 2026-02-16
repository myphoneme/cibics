import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { api, setAuthToken } from '../api/client';
import type { User } from '../types';

interface AuthContextShape {
  token: string | null;
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextShape | undefined>(undefined);

const TOKEN_KEY = 'cibics_token';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    refreshUser().finally(() => setLoading(false));
  }, [token]);

  async function refreshUser() {
    if (!token) {
      setUser(null);
      return;
    }

    try {
      const { data } = await api.get<User>('/auth/me');
      setUser(data);
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
    }
  }

  async function login(email: string, password: string) {
    const { data } = await api.post<{ access_token: string }>('/auth/login', { email, password });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setAuthToken(data.access_token);
    const me = await api.get<User>('/auth/me');
    setUser(me.data);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setAuthToken(null);
  }

  const value = useMemo(
    () => ({ token, user, loading, login, logout, refreshUser }),
    [token, user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return ctx;
}
