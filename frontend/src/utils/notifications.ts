// Push notification helpers \u2014 Expo + Emergent relay.

import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { api } from "@/src/api/client";

/**
 * Permission \u2192 native token \u2192 backend register. Safe to call repeatedly.
 * - Returns the device token (or null on failure / non-physical device).
 * - On web or simulator: no-ops.
 */
export async function registerForPush(
  authToken: string | null,
  userId: string | null,
): Promise<string | null> {
  if (!authToken || !userId) return null;
  if (Platform.OS === "web") return null;
  // On simulators, push tokens can't be acquired \u2014 skip silently.
  if (!Device.isDevice) return null;

  try {
    const existing = await Notifications.getPermissionsAsync();
    let status = existing.status;
    if (status !== "granted" && existing.canAskAgain !== false) {
      const req = await Notifications.requestPermissionsAsync();
      status = req.status;
    }
    if (status !== "granted") return null;

    const tokenResp = await Notifications.getDevicePushTokenAsync();
    const deviceToken = tokenResp?.data;
    if (!deviceToken) return null;

    const platform: "ios" | "android" = Platform.OS === "ios" ? "ios" : "android";
    // Register with Emergent relay (via backend) AND save in user record.
    await Promise.allSettled([
      api.registerPush(authToken, {
        user_id: userId,
        platform,
        device_token: String(deviceToken),
      }),
      api.savePushToken(authToken, {
        push_token: String(deviceToken),
        platform,
      }),
    ]);
    return String(deviceToken);
  } catch (err) {
    if (__DEV__) console.warn("[push] registration skipped:", err);
    return null;
  }
}
