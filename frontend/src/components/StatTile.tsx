// Stat tile — small card showing a number + label

import { Feather } from "@expo/vector-icons";
import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";

import { colors, radius, shadow, typography } from "@/src/theme";

type Props = {
  label: string;
  value: string | number;
  icon?: keyof typeof Feather.glyphMap;
  tone?: "default" | "success" | "danger" | "warning";
  testID?: string;
  style?: ViewStyle;
};

export function StatTile({ label, value, icon, tone = "default", testID, style }: Props) {
  const tint =
    tone === "success"
      ? colors.success
      : tone === "danger"
        ? colors.danger
        : tone === "warning"
          ? colors.warning
          : colors.primary;
  return (
    <View testID={testID} style={[styles.tile, style]}>
      <View style={styles.headerRow}>
        {icon ? (
          <View style={[styles.iconBubble, { backgroundColor: tint + "22" }]}>
            <Feather name={icon} size={14} color={tint} />
          </View>
        ) : null}
        <Text style={styles.label} numberOfLines={1}>
          {label}
        </Text>
      </View>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tile: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: 14,
    ...shadow.card,
    flex: 1,
    minWidth: 140,
  },
  headerRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 },
  iconBubble: { width: 24, height: 24, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  label: { ...typography.caption, color: colors.textSecondary, flex: 1 },
  value: { ...typography.title1, color: colors.textPrimary, fontSize: 24 },
});
