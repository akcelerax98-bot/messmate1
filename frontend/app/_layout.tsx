import * as Notifications from "expo-notifications";
import { Stack, useRouter } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import * as Linking from "expo-linking";
import React, { useEffect } from "react";
import { LogBox, Platform, StatusBar } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AuthProvider, useAuth, useAuthRouting } from "@/src/auth/AuthContext";
import { useIconFonts } from "@/src/hooks/use-icon-fonts";
import { ThemeProvider, useTheme } from "@/src/theme";
import { registerForPush } from "@/src/utils/notifications";

LogBox.ignoreAllLogs(true);

// Keep the native splash visible from cold start until icon fonts register.
SplashScreen.preventAutoHideAsync();

// ---------------------------------------------------------------------------
// Push notification setup \u2014 MUST be at module scope (per Emergent playbook).
// ---------------------------------------------------------------------------
if (Platform.OS !== "web") {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

if (Platform.OS === "android") {
  // Fire-and-forget; channel must exist before any push arrives.
  Notifications.setNotificationChannelAsync("default", {
    name: "Default",
    importance: Notifications.AndroidImportance.MAX,
    sound: "default",
    vibrationPattern: [0, 250, 250, 250],
  }).catch(() => {});
  Notifications.setNotificationChannelAsync("reminders", {
    name: "Meal reminders",
    importance: Notifications.AndroidImportance.HIGH,
    sound: "default",
  }).catch(() => {});
}

function RoutingShell() {
  useAuthRouting();
  const { c, isDark } = useTheme();
  return (
    <>
      <StatusBar
        barStyle={isDark ? "light-content" : "dark-content"}
        backgroundColor={c.bg}
      />
      <Stack
        screenOptions={{
          headerShown: false,
          animation: "fade",
          contentStyle: { backgroundColor: c.bg },
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(student)" />
        <Stack.Screen name="(admin)" />
        <Stack.Screen
          name="notifications"
          options={{ presentation: "modal", animation: "slide_from_bottom" }}
        />
      </Stack>
    </>
  );
}

function PushBridge() {
  const router = useRouter();
  const { token, user } = useAuth();

  // Register the device token whenever an authenticated user is active.
  useEffect(() => {
    if (!token || !user) return;
    registerForPush(token, user.id).catch(() => {});
  }, [token, user]);

  // Tap handlers: warm tap + cold start.
  useEffect(() => {
    if (Platform.OS === "web") return;

    const route = (url: string) => {
      try {
        if (url.startsWith("http")) {
          Linking.openURL(url);
        } else {
          router.push(url as any);
        }
      } catch {
        /* noop */
      }
    };

    const tapSub = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = (response.notification.request.content.data || {}) as Record<string, any>;
      const url = data.deeplink || data.action_url || "/notifications";
      route(String(url));
    });

    Notifications.getLastNotificationResponseAsync().then((response) => {
      if (!response) return;
      const data = (response.notification.request.content.data || {}) as Record<string, any>;
      const url = data.deeplink || data.action_url || "/notifications";
      route(String(url));
    });

    return () => {
      tapSub.remove();
    };
  }, [router]);

  return null;
}

export default function RootLayout() {
  const [loaded, error] = useIconFonts();

  useEffect(() => {
    if (loaded || error) {
      SplashScreen.hideAsync();
    }
  }, [loaded, error]);

  if (!loaded && !error) return null;

  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <AuthProvider>
          <PushBridge />
          <RoutingShell />
        </AuthProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
