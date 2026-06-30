// Theme system with light + dark + system mode

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Appearance } from "react-native";

import { storage } from "@/src/utils/storage";

const THEME_KEY = "messmate.theme";

export type ThemeMode = "light" | "dark" | "system";

const LIGHT = {
  mode: "light" as const,
  bg: "#F7F8FA",
  bg2: "#FFFFFF",
  card: "#FFFFFF",
  cardGlass: "rgba(255,255,255,0.85)",
  inputBg: "#F2F2F7",
  overlay: "rgba(0,0,0,0.40)",
  textPrimary: "#111827",
  textSecondary: "#6B7280",
  textTertiary: "#9CA3AF",
  textInverse: "#FFFFFF",
  primary: "#22C55E",
  primaryDark: "#15803D",
  primaryLight: "#EAFBF0",
  primaryTint: "rgba(34,197,94,0.12)",
  success: "#16A34A",
  warning: "#F59E0B",
  danger: "#EF4444",
  info: "#3B82F6",
  border: "rgba(0,0,0,0.06)",
  divider: "#E5E7EB",
  tabBarBg: "rgba(255,255,255,0.78)",
  tabBarBorder: "rgba(0,0,0,0.06)",
  badgePendingBg: "#FFFBEB",
  badgePendingText: "#F59E0B",
  badgeApprovedBg: "#EAFBF0",
  badgeApprovedText: "#15803D",
  badgeBlockedBg: "#FEF2F2",
  badgeBlockedText: "#EF4444",
};

const DARK = {
  mode: "dark" as const,
  bg: "#0B0F0D",
  bg2: "#111827",
  card: "#1E293B",
  cardGlass: "rgba(30,41,59,0.72)",
  inputBg: "#1F2937",
  overlay: "rgba(0,0,0,0.65)",
  textPrimary: "#F9FAFB",
  textSecondary: "#9CA3AF",
  textTertiary: "#6B7280",
  textInverse: "#0B0F0D",
  primary: "#22C55E",
  primaryDark: "#16A34A",
  primaryLight: "#14532D",
  primaryTint: "rgba(34,197,94,0.20)",
  success: "#22C55E",
  warning: "#FBBF24",
  danger: "#F87171",
  info: "#60A5FA",
  border: "rgba(255,255,255,0.10)",
  divider: "rgba(255,255,255,0.08)",
  tabBarBg: "rgba(17,24,39,0.78)",
  tabBarBorder: "rgba(255,255,255,0.08)",
  badgePendingBg: "rgba(245,158,11,0.15)",
  badgePendingText: "#FBBF24",
  badgeApprovedBg: "rgba(34,197,94,0.15)",
  badgeApprovedText: "#22C55E",
  badgeBlockedBg: "rgba(239,68,68,0.15)",
  badgeBlockedText: "#F87171",
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

type Ctx = {
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  c: ThemeColors;
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

  const value = useMemo(() => ({ mode, setMode, c }), [mode, setMode, c]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

// Legacy export for files that still import { colors } directly
// They will render in light-mode colors only — use useTheme() for dynamic theming.
export const colors = LIGHT;
