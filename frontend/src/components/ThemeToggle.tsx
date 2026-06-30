// Theme picker — Light / Dark / System (pill segmented).

import { Feather } from "@expo/vector-icons";
import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { spacing, typography, useTheme, type ThemeMode } from "@/src/theme";

const OPTIONS: { value: ThemeMode; label: string; icon: keyof typeof Feather.glyphMap }[] = [
  { value: "light", label: "Light", icon: "sun" },
  { value: "dark", label: "Dark", icon: "moon" },
  { value: "system", label: "System", icon: "smartphone" },
];

export function ThemeToggle() {
  const { mode, setMode, c } = useTheme();
  return (
    <View style={[styles.wrap, { backgroundColor: c.inputBg }]} testID="theme-toggle">
      {OPTIONS.map((opt) => {
        const active = opt.value === mode;
        return (
          <TouchableOpacity
            key={opt.value}
            testID={`theme-toggle-${opt.value}`}
            activeOpacity={0.85}
            onPress={() => setMode(opt.value)}
            style={[
              styles.seg,
              active && { backgroundColor: c.card, ...styles.activeShadow },
            ]}
          >
            <Feather
              name={opt.icon}
              size={14}
              color={active ? c.primary : c.textSecondary}
            />
            <Text
              style={[
                styles.label,
                { color: active ? c.textPrimary : c.textSecondary },
              ]}
            >
              {opt.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: "row", borderRadius: 14, padding: 3, gap: 3 },
  seg: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 11,
  },
  activeShadow: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 1,
  },
  label: { ...typography.footnote, fontWeight: "600" },
});

// re-export so files can keep importing from theme directly
export { spacing, typography };
