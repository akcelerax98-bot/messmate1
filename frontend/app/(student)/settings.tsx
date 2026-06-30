import React from "react";

import { PlaceholderScreen } from "@/src/components/PlaceholderScreen";

export default function StudentSettings() {
  return (
    <PlaceholderScreen
      testID="student-settings"
      title="Settings"
      icon="settings"
      description="Student profile and app settings will be built here."
      showLogout
    />
  );
}
