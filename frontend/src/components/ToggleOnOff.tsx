// ON/OFF toggle — pill segmented control. Theme-reactive.

import React, { useMemo } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { typography, useTheme, type ThemeColors } from "@/src/theme";

type Props = {
  value: "ON" | "OFF" | null;
  onChange: (v: "ON" | "OFF") => void;
  testIDPrefix: string;
};

export function ToggleOnOff({ value, onChange, testIDPrefix }: Props) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  return (
    <View style={styles.wrap}>
      <TouchableOpacity
        testID={`${testIDPrefix}-on`}
        activeOpacity={0.85}
        onPress={() => onChange("ON")}
        style={[styles.btn, value === "ON" && { backgroundColor: c.primary }]}
      >
        <Text style={[styles.label, { color: value === "ON" ? c.textInverse : c.textPrimary }]}>
          ON
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        testID={`${testIDPrefix}-off`}
        activeOpacity={0.85}
        onPress={() => onChange("OFF")}
        style={[styles.btn, value === "OFF" && { backgroundColor: c.danger }]}
      >
        <Text style={[styles.label, { color: value === "OFF" ? c.textInverse : c.textPrimary }]}>
          OFF
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    wrap: {
      flexDirection: "row",
      backgroundColor: c.inputBg,
      borderRadius: 12,
      padding: 3,
      gap: 3,
    },
    btn: {
      paddingHorizontal: 18,
      paddingVertical: 8,
      borderRadius: 10,
      minWidth: 64,
      alignItems: "center",
      justifyContent: "center",
    },
    label: { ...typography.footnote, fontWeight: "700", letterSpacing: 0.5 },
  });
