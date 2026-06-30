// Theme system with light + dark + system mode — globally reactive.
//
// All UI screens that need theming should call `useTheme()` and read `c.<key>`.
// Some legacy files import the static `colors` export — that export is a
// live proxy that reads from a module-scope mutable palette so dynamic values
// flow through even though `StyleSheet.create()` only runs once. (Layouts that
// hardcoded `colors.xxx` in a frozen StyleSheet should override the colored
// properties inline with `c.xxx` at render time.)

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Appearance } from "react-native";

import { storage } from "@/src/utils/storage";

const THEME_KEY = "messmate.theme";

export type ThemeMode = "light" | "dark" | "system";

const LIGHT = {
  mode: "light" as const,
  bg: "#F6F7FB",
  bg2: "#FFFFFF",
  card: "#FFFFFF",
  cardGlass: "rgba(255,255,255,0.85)",
  inputBg: "#F2F2F7",
  overlay: "rgba(0,0,0,0.40)",
  textPrimary: "#0B1220",
  textSecondary: "#5B6675",
  textTertiary: "#9CA3AF",
  textInverse: "#FFFFFF",
  primary: "#22C55E",
  primaryDark: "#15803D",
  primaryLight: "#EAFBF0",
  primaryTint: "rgba(34,197,94,0.12)",
  pending: "#F59E0B",
  success: "#16A34A",
  warning: "#F59E0B",
  danger: "#EF4444",
  info: "#3B82F6",
  border: "rgba(0,0,0,0.06)",
  divider: "#E5E7EB",
  tabBarBg: "rgba(255,255,255,0.65)",
  tabBarBorder: "rgba(0,0,0,0.06)",
  tabBarBlurTint: "light" as "light" | "dark" | "default",
  tabBarActivePill: "rgba(34,197,94,0.14)",
  badgePendingBg: "#FFFBEB",
  badgePendingText: "#F59E0B",
  badgeApprovedBg: "#EAFBF0",
  badgeApprovedText: "#15803D",
  badgeBlockedBg: "#FEF2F2",
  badgeBlockedText: "#EF4444",
  shimmer: "rgba(0,0,0,0.06)",
};

const DARK: typeof LIGHT = {
  mode: "dark" as any,
  bg: "#0A0F14",
  bg2: "#0F1622",
  card: "#141B27",
  cardGlass: "rgba(20,27,39,0.72)",
  inputBg: "#1C2433",
  overlay: "rgba(0,0,0,0.65)",
  textPrimary: "#F4F6FB",
  textSecondary: "#A3ADBC",
  textTertiary: "#6B7280",
  textInverse: "#0A0F14",
  primary: "#34D17A",
  primaryDark: "#16A34A",
  primaryLight: "rgba(52,209,122,0.18)",
  primaryTint: "rgba(52,209,122,0.20)",
  pending: "#FBBF24",
  success: "#22C55E",
  warning: "#FBBF24",
  danger: "#F87171",
  info: "#60A5FA",
  border: "rgba(255,255,255,0.08)",
  divider: "rgba(255,255,255,0.06)",
  tabBarBg: "rgba(20,27,39,0.55)",
  tabBarBorder: "rgba(255,255,255,0.07)",
  tabBarBlurTint: "dark",
  tabBarActivePill: "rgba(52,209,122,0.20)",
  badgePendingBg: "rgba(251,191,36,0.15)",
  badgePendingText: "#FBBF24",
  badgeApprovedBg: "rgba(34,197,94,0.18)",
  badgeApprovedText: "#34D17A",
  badgeBlockedBg: "rgba(248,113,113,0.18)",
  badgeBlockedText: "#F87171",
  shimmer: "rgba(255,255,255,0.06)",
};

export type ThemeColors = typeof LIGHT;

export const spacing = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 };
export const radius = { sm: 8, md: 14, lg: 18, xl: 24, pill: 9999 };
export const typography = {
  largeTitle: { fontSize: 32, fontWeight: "700" as const, letterSpacing: -0.5 },
  title1: { fontSize: 26, fontWeight: "700" as const },
  title2: { fontSize: 20, fontWeight: "700" as const },
  headline: { fontSize: 17, fontWeight: "600" as const, letterSpacing: -0.3 },
  body: { fontSize: 16, fontWeight: "400" as const },
  callout: { fontSize: 15, fontWeight: "400" as const },
  subhead: { fontSize: 14, fontWeight: "400" as const },
  footnote: { fontSize: 13, fontWeight: "500" as const },
  caption: { fontSize: 12, fontWeight: "400" as const },
};
export const shadow = {
  card: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.06,
    shadowRadius: 16,
    elevation: 2,
  },
  glass: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.10,
    shadowRadius: 24,
    elevation: 6,
  },
};

// ---------------------------------------------------------------------------
// Live palette — read by both `useTheme()` and the legacy `colors` proxy.
// ---------------------------------------------------------------------------
let _active: ThemeColors = LIGHT;
const _listeners = new Set<() => void>();

function setActive(next: ThemeColors) {
  if (next === _active) return;
  _active = next;
  _listeners.forEach((fn) => {
    try { fn(); } catch { /* noop */ }
  });
}

type Ctx = {
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  c: ThemeColors;
  isDark: boolean;
};

const ThemeContext = createContext<Ctx | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>("system");
  const [system, setSystem] = useState<"light" | "dark">(
    Appearance.getColorScheme() === "dark" ? "dark" : "light",
  );

  useEffect(() => {
    (async () => {
      const saved = await storage.getItem(THEME_KEY, "system");
      if (saved === "light" || saved === "dark" || saved === "system") {
        setModeState(saved);
      }
    })();
    const sub = Appearance.addChangeListener(({ colorScheme }) => {
      setSystem(colorScheme === "dark" ? "dark" : "light");
    });
    return () => sub.remove();
  }, []);

  const setMode = useCallback((m: ThemeMode) => {
    setModeState(m);
    storage.setItem(THEME_KEY, m);
  }, []);

  const effective = mode === "system" ? system : mode;
  const c = effective === "dark" ? DARK : LIGHT;

  // Keep the live palette in sync so the legacy `colors` proxy serves the
  // currently active palette.
  useEffect(() => {
    setActive(c);
  }, [c]);

  const value = useMemo<Ctx>(
    () => ({ mode, setMode, c, isDark: effective === "dark" }),
    [mode, setMode, c, effective],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

// ---------------------------------------------------------------------------
// Legacy live proxy — `colors.xxx` always reflects the active palette.
// NOTE: values read at JSX render time work. Values read inside
// `StyleSheet.create({...})` are frozen at module load; for those, screens
// override the relevant style properties inline with `c.xxx`.
// ---------------------------------------------------------------------------
export const colors: ThemeColors = new Proxy({} as ThemeColors, {
  get(_t, key: string) {
    return (_active as any)[key];
  },
}) as ThemeColors;
