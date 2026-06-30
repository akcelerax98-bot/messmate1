import React from "react";

import { PlaceholderScreen } from "@/src/components/PlaceholderScreen";

export default function AdminSettings() {
  return (
    <PlaceholderScreen
      testID="admin-settings"
      title="Settings"
      icon="settings"
      description="Admin settings and default app states will be built here."
      showLogout
    />
  );
}
