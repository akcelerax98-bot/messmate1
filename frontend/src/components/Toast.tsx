// Lightweight toast — slides down from top, auto-dismisses. Theme-reactive.

import React, { useEffect, useRef } from "react";
import { Animated, StyleSheet, Text } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { radius, typography, useTheme } from "@/src/theme";

type Props = {
  message: string | null;
  variant?: "success" | "error" | "info";
  onHide: () => void;
  testID?: string;
};

export function Toast({ message, variant = "success", onHide, testID }: Props) {
  const { c } = useTheme();
  const insets = useSafeAreaInsets();
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(-20)).current;

  useEffect(() => {
    if (!message) return;
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start();

    const timer = setTimeout(() => {
      Animated.parallel([
        Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }),
        Animated.timing(translateY, { toValue: -20, duration: 200, useNativeDriver: true }),
      ]).start(() => onHide());
    }, 2200);

    return () => clearTimeout(timer);
  }, [message, opacity, translateY, onHide]);

  if (!message) return null;

  const bg = variant === "error" ? c.danger : variant === "info" ? c.textPrimary : c.primary;
  const textColor = variant === "info" ? c.textInverse : "#fff";

  return (
    <Animated.View
      testID={testID}
      pointerEvents="none"
      style={[
        styles.toast,
        {
          top: insets.top + 8,
          opacity,
          transform: [{ translateY }],
          backgroundColor: bg,
        },
      ]}
    >
      <Text style={[styles.text, { color: textColor }]}>{message}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  toast: {
    position: "absolute",
    left: 16,
    right: 16,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: radius.md,
    zIndex: 999,
    elevation: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
  },
  text: { ...typography.subhead, textAlign: "center", fontWeight: "600" },
});
