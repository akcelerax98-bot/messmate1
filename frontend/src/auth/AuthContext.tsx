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
import { Alert } from "react-native";

import { api, setSessionInvalidatedHandler, type TokenResponse, type User } from "@/src/api/client";
import { storage } from "@/src/utils/storage";

const TOKEN_KEY = "messmate.jwt";
const USER_KEY = "messmate.user";

type AuthState = {
  token: string | null;
  user: User | null;
  loading: boolean;
};

type AuthContextValue = AuthState & {
  /** Persist a TokenResponse (used by all auth flows that return a JWT). */
  setSession: (resp: TokenResponse) => Promise<User>;
  /** Email + password login. Throws on bad creds or unverified email. */
  loginEmail: (payload: { email: string; password: string }) => Promise<User>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const savedToken = await storage.secureGet(TOKEN_KEY, "");
      const savedUserRaw = await storage.getItem(USER_KEY, "");
      if (savedToken && savedUserRaw) {
        try {
          const parsed = JSON.parse(savedUserRaw as string) as User;
          setToken(savedToken as string);
          setUser(parsed);
          // Verify the session with the backend. If it was invalidated (another
          // device signed in), the api client's session-invalidated handler
          // will fire and log us out.
          try {
            const fresh = await api.me(savedToken as string);
            setUser(fresh);
            await storage.setItem(USER_KEY, JSON.stringify(fresh));
          } catch {
            // ignore — handler above will log out if session_invalidated
          }
        } catch {
          await storage.secureRemove(TOKEN_KEY);
          await storage.removeItem(USER_KEY);
        }
      }
      setLoading(false);
    })();
  }, []);

  const setSession: AuthContextValue["setSession"] = useCallback(async (resp) => {
    await storage.secureSet(TOKEN_KEY, resp.access_token);
    await storage.setItem(USER_KEY, JSON.stringify(resp.user));
    setToken(resp.access_token);
    setUser(resp.user);
    return resp.user;
  }, []);

  const loginEmail: AuthContextValue["loginEmail"] = useCallback(
    async (payload) => {
      const resp = await api.login(payload);
      return await setSession(resp);
    },
    [setSession],
  );

  const logout = useCallback(async () => {
    await storage.secureRemove(TOKEN_KEY);
    await storage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // Register a handler so the API client can auto-logout when the server tells
  // us the session was superseded on another device.
  useEffect(() => {
    setSessionInvalidatedHandler((message) => {
      // Fire-and-forget; we don't need to await the storage clears.
      void logout();
      Alert.alert("Signed out", message);
    });
    return () => setSessionInvalidatedHandler(null);
  }, [logout]);

  const value = useMemo(
    () => ({ token, user, loading, setSession, loginEmail, logout }),
    [token, user, loading, setSession, loginEmail, logout],
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
      const path = segments.join("/");
      if (
        top === "(student)" ||
        top === "(admin)" ||
        path === "(auth)/pending" ||
        path === "(auth)/blocked"
      ) {
        target = "/";
      }
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
