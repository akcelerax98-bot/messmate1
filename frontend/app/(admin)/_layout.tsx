// Admin tab navigator — 5 tabs, liquid-glass floating pill.

import { Tabs } from "expo-router";
import React from "react";

import { GlassTabBar, type TabIconMap } from "@/src/components/GlassTabBar";
import { useTheme } from "@/src/theme";

const icons: TabIconMap = {
  "students-status": "users",
  dashboard: "grid",
  "wastage-calc": "bar-chart-2",
  "necessary-info": "clipboard",
  settings: "settings",
};

export default function AdminTabsLayout() {
  const { c } = useTheme();
  return (
    <Tabs
      tabBar={(props) => <GlassTabBar {...props} icons={icons} />}
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: c.bg },
      }}
    >
      <Tabs.Screen name="students-status" options={{ title: "Students" }} />
      <Tabs.Screen name="dashboard" options={{ title: "Dashboard" }} />
      <Tabs.Screen name="wastage-calc" options={{ title: "Wastage" }} />
      <Tabs.Screen name="necessary-info" options={{ title: "Info" }} />
      <Tabs.Screen name="settings" options={{ title: "Settings" }} />
    </Tabs>
  );
}
