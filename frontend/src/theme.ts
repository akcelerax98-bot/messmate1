// MessMate theme tokens — Apple-style premium aesthetic with green sustainability accent.
// Source: /app/design_guidelines.json

export const colors = {
  primary: "#248243",
  primaryLight: "#E8F5E9",
  primaryDark: "#1A4D2E",

  bg: "#F9F9F9",
  card: "#FFFFFF",
  inputBg: "#F2F2F7",
  overlay: "rgba(0,0,0,0.4)",

  textPrimary: "#1C1C1E",
  textSecondary: "#8E8E93",
  textTertiary: "#C7C7CC",
  textInverse: "#FFFFFF",

  success: "#34C759",
  danger: "#FF3B30",
  warning: "#FF9500",
  pending: "#F59E0B",

  border: "#E5E5EA",

  badgePendingBg: "#FFFBEB",
  badgePendingText: "#F59E0B",
  badgeApprovedBg: "#E8F5E9",
  badgeApprovedText: "#248243",
  badgeBlockedBg: "#FEF2F2",
  badgeBlockedText: "#FF3B30",
};

export const spacing = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 };

export const radius = {
  sm: 8,
  md: 14,
  lg: 16,
  xl: 24,
  pill: 9999,
};

export const typography = {
  largeTitle: { fontSize: 34, fontWeight: "700" as const, letterSpacing: -0.5 },
  title1: { fontSize: 28, fontWeight: "700" as const },
  title2: { fontSize: 22, fontWeight: "600" as const },
  headline: { fontSize: 17, fontWeight: "600" as const, letterSpacing: -0.4 },
  body: { fontSize: 17, fontWeight: "400" as const, letterSpacing: -0.4 },
  callout: { fontSize: 16, fontWeight: "400" as const, letterSpacing: -0.3 },
  subhead: { fontSize: 15, fontWeight: "400" as const, letterSpacing: -0.2 },
  footnote: { fontSize: 13, fontWeight: "500" as const },
  caption: { fontSize: 12, fontWeight: "400" as const },
};

export const shadow = {
  card: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.05,
    shadowRadius: 24,
    elevation: 2,
  },
};
