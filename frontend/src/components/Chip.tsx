// Multi-select / single-select chip used for preferences, reactions, and options.

import React from "react";
import { StyleSheet, Text, TouchableOpacity, ViewStyle } from "react-native";

import { colors, radius, typography } from "@/src/theme";

type Props = {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  testID?: string;
  variant?: "default" | "danger" | "success";
  style?: ViewStyle;
};

export function Chip({ label, selected, onPress, testID, variant = "default", style }: Props) {
  const bg = selected
    ? variant === "danger"
      ? colors.danger
      : variant === "success"
        ? colors.success
        : colors.primary
    : colors.inputBg;
  const text = selected ? colors.textInverse : colors.textPrimary;

  return (
    <TouchableOpacity
      testID={testID}
      onPress={onPress}
      activeOpacity={0.85}
      style={[styles.chip, { backgroundColor: bg }, style]}
    >
      <Text style={[styles.label, { color: text }]} numberOfLines={1}>
        {label}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  chip: {
    height: 36,
    paddingHorizontal: 16,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  label: { ...typography.subhead, fontWeight: "600" },
});
