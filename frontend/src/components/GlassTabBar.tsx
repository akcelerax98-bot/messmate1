// Liquid-glass animated tab bar. Pure JS reanimated active pill on top of
// an Expo BlurView panel. Shared between Student and Admin tab navigators.

import { Feather } from "@expo/vector-icons";
import { BlurView } from "expo-blur";
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import React, { useEffect, useState } from "react";
import { LayoutChangeEvent, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from "react-native-reanimated";

import { useTheme } from "@/src/theme";

export type TabIconMap = Record<string, keyof typeof Feather.glyphMap>;

export function GlassTabBar({
  state,
  descriptors,
  navigation,
  icons,
}: BottomTabBarProps & { icons: TabIconMap }) {
  const { c, isDark } = useTheme();
  const tabCount = state.routes.length;
  const [trackWidth, setTrackWidth] = useState(0);
  const pillX = useSharedValue(0);
  const scale = useSharedValue(1);

  // Animate the active pill into position with a tiny scale bounce.
  useEffect(() => {
    pillX.value = withSpring(state.index, { damping: 18, stiffness: 200, mass: 0.6 });
    scale.value = withSpring(1.06, { damping: 14, stiffness: 220 });
    const t = setTimeout(() => {
      scale.value = withSpring(1, { damping: 18, stiffness: 220 });
    }, 120);
    return () => clearTimeout(t);
  }, [state.index, pillX, scale]);

  const pillWidth = trackWidth > 0 ? trackWidth / tabCount : 0;

  const animatedPill = useAnimatedStyle(() => ({
    transform: [
      { translateX: pillX.value * pillWidth },
      { scale: scale.value },
    ],
    width: pillWidth,
  }));

  const onTrackLayout = (e: LayoutChangeEvent) => {
    setTrackWidth(e.nativeEvent.layout.width);
  };

  return (
    <View pointerEvents="box-none" style={styles.wrapper}>
      <View
        style={[
          styles.shadowHost,
          { borderColor: c.tabBarBorder },
        ]}
      >
        <BlurView
          intensity={Platform.OS === "ios" ? 60 : 40}
          tint={c.tabBarBlurTint as any}
          style={StyleSheet.absoluteFill}
        />
        <View
          pointerEvents="none"
          style={[
            StyleSheet.absoluteFill,
            { backgroundColor: c.tabBarBg },
          ]}
        />
        {/* Animated active pill on a measured track */}
        <View
          pointerEvents="none"
          style={styles.pillTrack}
          onLayout={onTrackLayout}
        >
          {pillWidth > 0 ? (
            <Animated.View
              style={[
                styles.pill,
                {
                  backgroundColor: c.tabBarActivePill,
                  borderColor: isDark
                    ? "rgba(255,255,255,0.06)"
                    : "rgba(0,0,0,0.04)",
                },
                animatedPill,
              ]}
            />
          ) : null}
        </View>
        <View style={styles.tabsRow}>
          {state.routes.map((route, idx) => {
            const { options } = descriptors[route.key];
            const label =
              (options.tabBarLabel as string) ||
              (options.title as string) ||
              route.name;
            const isFocused = state.index === idx;
            const iconName = icons[route.name] || "circle";

            const onPress = () => {
              const event = navigation.emit({
                type: "tabPress",
                target: route.key,
                canPreventDefault: true,
              });
              if (!isFocused && !event.defaultPrevented) {
                navigation.navigate(route.name as never);
              }
            };

            const onLongPress = () => {
              navigation.emit({ type: "tabLongPress", target: route.key });
            };

            return (
              <Pressable
                key={route.key}
                accessibilityRole="button"
                accessibilityState={isFocused ? { selected: true } : {}}
                onPress={onPress}
                onLongPress={onLongPress}
                style={styles.tab}
                testID={`tab-${route.name}`}
                android_ripple={{ color: "transparent" }}
              >
                <Feather
                  name={iconName}
                  size={20}
                  color={isFocused ? c.primary : c.textSecondary}
                />
                <Text
                  numberOfLines={1}
                  style={[
                    styles.label,
                    {
                      color: isFocused ? c.primary : c.textSecondary,
                      fontWeight: isFocused ? "700" : "600",
                    },
                  ]}
                >
                  {label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    position: "absolute",
    left: 14,
    right: 14,
    bottom: Platform.OS === "ios" ? 24 : 14,
  },
  shadowHost: {
    height: 68,
    borderRadius: 30,
    overflow: "hidden",
    borderWidth: 1,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.12,
    shadowRadius: 22,
    elevation: 12,
  },
  pillTrack: {
    position: "absolute",
    top: 8,
    bottom: 8,
    left: 6,
    right: 6,
  },
  pill: {
    position: "absolute",
    top: 0,
    bottom: 0,
    left: 0,
    borderRadius: 22,
    borderWidth: 1,
  },
  tabsRow: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 6,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 3,
    paddingVertical: 8,
  },
  label: { fontSize: 10.5, letterSpacing: 0.2 },
});
