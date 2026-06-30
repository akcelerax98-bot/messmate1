// Student tab navigator — 4 tabs, liquid-glass floating pill.

import { Tabs } from "expo-router";
import React from "react";

import { GlassTabBar, type TabIconMap } from "@/src/components/GlassTabBar";
import { useTheme } from "@/src/theme";

const icons: TabIconMap = {
  home: "home",
  menu: "calendar",
  wastage: "pie-chart",
  settings: "settings",
};

export default function StudentTabsLayout() {
  const { c } = useTheme();
  return (
    <Tabs
      tabBar={(props) => <GlassTabBar {...props} icons={icons} />}
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: c.bg },
      }}
    >
      <Tabs.Screen name="home" options={{ title: "Today" }} />
      <Tabs.Screen name="menu" options={{ title: "Menu" }} />
      <Tabs.Screen name="wastage" options={{ title: "Wastage" }} />
      <Tabs.Screen name="settings" options={{ title: "Settings" }} />
    </Tabs>
  );
}
