// Notifications bell button — used in tab headers / corners.

import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { api } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { typography, useTheme } from "@/src/theme";

export function NotifBell({ testID = "notif-bell" }: { testID?: string }) {
  const { c } = useTheme();
  const router = useRouter();
  const { token, user } = useAuth();
  const [unread, setUnread] = useState(0);

  const fetchCount = useCallback(async () => {
    if (!token || user?.role !== "student") return;
    try {
      const res = await api.studentNotifications(token);
      setUnread(res.unread_count);
    } catch {
      /* silent */
    }
  }, [token, user?.role]);

  useEffect(() => {
    fetchCount();
    const t = setInterval(fetchCount, 30_000);
    return () => clearInterval(t);
  }, [fetchCount]);

  return (
    <TouchableOpacity
      testID={testID}
      activeOpacity={0.85}
      onPress={() => router.push("/notifications")}
      style={[styles.btn, { backgroundColor: c.inputBg }]}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
    >
      <Feather name="bell" size={18} color={c.textPrimary} />
      {unread > 0 ? (
        <View style={[styles.badge, { backgroundColor: c.danger }]}>
          <Text style={styles.badgeText}>{unread > 9 ? "9+" : String(unread)}</Text>
        </View>
      ) : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  badge: {
    position: "absolute",
    top: 4,
    right: 4,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    paddingHorizontal: 4,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: { ...typography.caption, color: "#fff", fontWeight: "700", fontSize: 10 },
});
