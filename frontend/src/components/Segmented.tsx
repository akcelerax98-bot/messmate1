// Segmented control — Apple-style. Pill row with selected segment highlighted.

import React from "react";
import { StyleSheet, Text, TouchableOpacity, View, ViewStyle } from "react-native";

import { colors, typography } from "@/src/theme";

type Option<T extends string> = { value: T; label: string; testID?: string };

type Props<T extends string> = {
  options: Option<T>[];
  value: T;
  onChange: (v: T) => void;
  testID?: string;
  style?: ViewStyle;
};

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  testID,
  style,
}: Props<T>) {
  return (
    <View testID={testID} style={[styles.wrap, style]}>
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <TouchableOpacity
            key={opt.value}
            testID={opt.testID}
            activeOpacity={0.85}
            onPress={() => onChange(opt.value)}
            style={[styles.seg, active && styles.segActive]}
          >
            <Text
              style={[
                styles.label,
                { color: active ? colors.textPrimary : colors.textSecondary },
              ]}
              numberOfLines={1}
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
  wrap: {
    flexDirection: "row",
    backgroundColor: colors.inputBg,
    borderRadius: 12,
    padding: 3,
  },
  seg: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  segActive: {
    backgroundColor: colors.card,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 1,
  },
  label: { ...typography.footnote, fontWeight: "600" },
});
