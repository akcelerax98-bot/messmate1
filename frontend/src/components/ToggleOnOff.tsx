// ON/OFF toggle — pill segmented control showing the student's eating intent.

import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { colors, typography } from "@/src/theme";

type Props = {
  value: "ON" | "OFF" | null;
  onChange: (v: "ON" | "OFF") => void;
  testIDPrefix: string;
};

export function ToggleOnOff({ value, onChange, testIDPrefix }: Props) {
  return (
    <View style={styles.wrap}>
      <TouchableOpacity
        testID={`${testIDPrefix}-on`}
        activeOpacity={0.85}
        onPress={() => onChange("ON")}
        style={[
          styles.btn,
          value === "ON" && { backgroundColor: colors.primary },
        ]}
      >
        <Text
          style={[
            styles.label,
            { color: value === "ON" ? colors.textInverse : colors.textPrimary },
          ]}
        >
          ON
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        testID={`${testIDPrefix}-off`}
        activeOpacity={0.85}
        onPress={() => onChange("OFF")}
        style={[
          styles.btn,
          value === "OFF" && { backgroundColor: colors.danger },
        ]}
      >
        <Text
          style={[
            styles.label,
            { color: value === "OFF" ? colors.textInverse : colors.textPrimary },
          ]}
        >
          OFF
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    backgroundColor: colors.inputBg,
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
