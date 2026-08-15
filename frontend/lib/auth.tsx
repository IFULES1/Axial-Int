"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

export type User = {
  id: string;
  email: string;
  full_name: string | null;
  is_admin: boolean;
  onboarding_complete: boolean;
};

type TokenResponse = { access_token: string; refresh_token: string; user: User };

type AuthContextValue = {
  user: User | null;
  token: string | null;
  loading: boolean;
  register: (email: string, password: string, fullName?: string) => Promise<User>;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const STORAGE_KEY = "axial_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async (tok: string) => {
    try {
      const me = await api.get<User>("/auth/me", tok);
      setUser(me);
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      setToken(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setToken(stored);
      loadMe(stored).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [loadMe]);

  const persist = (res: TokenResponse) => {
    localStorage.setItem(STORAGE_KEY, res.access_token);
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const register = async (email: string, password: string, fullName?: string) => {
    const res = await api.post<TokenResponse>("/auth/register", {
      email,
      password,
      full_name: fullName ?? null,
    });
    return persist(res);
  };

  const login = async (email: string, password: string) => {
    const res = await api.post<TokenResponse>("/auth/login", { email, password });
    return persist(res);
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setUser(null);
  };

  const refresh = async () => {
    if (token) await loadMe(token);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, register, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
