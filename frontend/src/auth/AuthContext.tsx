// Auth context — persists JWT, exposes login/register/logout, drives role-based routing.

import { useRouter, useSegments } from "expo-router";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { api, type User } from "@/src/api/client";
import { storage } from "@/src/utils/storage";

const TOKEN_KEY = "messmate.jwt";
const USER_KEY = "messmate.user";

type AuthState = {
  token: string | null;
  user: User | null;
  loading: boolean;
};

type AuthContextValue = AuthState & {
  login: (payload: {
    mobile_or_user_id: string;
    password: string;
    institution_or_hostel_name?: string;
  }) => Promise<User>;
  registerStudent: (payload: {
    full_name: string;
    mobile_or_user_id: string;
    institution_or_hostel_name: string;
    room_number: string;
    password: string;
  }) => Promise<User>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore from storage on mount.
  useEffect(() => {
    (async () => {
      const savedToken = await storage.secureGet(TOKEN_KEY, "");
      const savedUserRaw = await storage.getItem(USER_KEY, "");
      if (savedToken && savedUserRaw) {
        try {
          const parsed = JSON.parse(savedUserRaw as string) as User;
          setToken(savedToken as string);
          setUser(parsed);
        } catch {
          await storage.secureRemove(TOKEN_KEY);
          await storage.removeItem(USER_KEY);
        }
      }
      setLoading(false);
    })();
  }, []);

  const login: AuthContextValue["login"] = useCallback(async (payload) => {
    const res = await api.login(payload);
    await storage.secureSet(TOKEN_KEY, res.access_token);
    await storage.setItem(USER_KEY, JSON.stringify(res.user));
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const registerStudent: AuthContextValue["registerStudent"] = useCallback(
    async (payload) => {
      return await api.registerStudent(payload);
    },
    [],
  );

  const logout = useCallback(async () => {
    await storage.secureRemove(TOKEN_KEY);
    await storage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ token, user, loading, login, registerStudent, logout }),
    [token, user, loading, login, registerStudent, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/**
 * Drives route protection. Runs once auth state is resolved.
 *  - approved admin   -> /(admin)
 *  - approved student -> /(student)
 *  - pending student  -> /(auth)/pending
 *  - blocked student  -> /(auth)/blocked
 *  - logged out       -> /
 */
export function useAuthRouting() {
  const { user, loading } = useAuth();
  const segments = useSegments();
  const router = useRouter();
  const lastTarget = useRef<string | null>(null);

  useEffect(() => {
    if (loading) return;
    const top = segments[0] as string | undefined;

    let target: string | null = null;
    if (!user) {
      // Allow staying on public pages (welcome + auth screens).
      if (top === "(student)" || top === "(admin)") target = "/";
    } else if (user.role === "admin") {
      if (top !== "(admin)") target = "/(admin)/students-status";
    } else {
      // student
      if (user.approval_status === "approved") {
        if (top !== "(student)") target = "/(student)/home";
      } else if (user.approval_status === "pending") {
        if (segments.join("/") !== "(auth)/pending") target = "/(auth)/pending";
      } else if (user.approval_status === "rejected_or_blocked") {
        if (segments.join("/") !== "(auth)/blocked") target = "/(auth)/blocked";
      }
    }

    if (target && lastTarget.current !== target) {
      lastTarget.current = target;
      router.replace(target as any);
    } else if (!target) {
      lastTarget.current = null;
    }
  }, [user, loading, segments, router]);
}
