// API client for MessMate backend.

const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

if (!BASE_URL) {
  console.warn("EXPO_PUBLIC_BACKEND_URL is not defined");
}

export type ApprovalStatus = "pending" | "approved" | "rejected_or_blocked";
export type Role = "student" | "admin";
export type MealStatus = "ON" | "OFF";
export type MealType = "breakfast" | "lunch" | "dinner";
export type Reaction = "like" | "dislike" | "no_response";
export type Unit = "pieces" | "grams" | "kg" | "ml" | "litres";

export type User = {
  id: string;
  full_name: string;
  mobile_or_user_id: string;
  institution_or_hostel_name: string;
  room_number?: string | null;
  role: Role;
  approval_status: ApprovalStatus;
  created_at: string;
  updated_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type CustomQuestion = { text: string; options: string[] } | null;

export type MealPlan = {
  status: MealStatus | null;
  selected_items: string[];
  reason_if_off: string | null;
  custom_answer: string | null;
};

export type DailyMenu = {
  day: string;
  breakfast_items: string[];
  lunch_items: string[];
  dinner_items: string[];
  breakfast_custom_question: CustomQuestion;
  lunch_custom_question: CustomQuestion;
  dinner_custom_question: CustomQuestion;
};

export type WeeklyDay = DailyMenu & {
  reactions: { breakfast: Reaction; lunch: Reaction; dinner: Reaction };
};

export type TodayResponse = {
  date: string;
  day: string;
  menu: DailyMenu | null;
  plan: {
    date: string;
    breakfast: Partial<MealPlan>;
    lunch: Partial<MealPlan>;
    dinner: Partial<MealPlan>;
    updated_at?: string;
  } | null;
};

export type WastageSummary = {
  today: {
    breakfast: number | null;
    lunch: number | null;
    dinner: number | null;
    total: number | null;
  };
  yesterday_total: number | null;
  last_week_same_day_total: number | null;
};

export type WastageResponse = {
  range: number;
  meal: "all" | MealType;
  series: { date: string; value: number }[];
  summary: WastageSummary;
};

// ---------- Admin types ----------
export type StudentsSummary = {
  total_students: number;
  approved: number;
  pending: number;
  blocked: number;
};

export type StudentRow = {
  id: string;
  full_name: string;
  mobile_or_user_id: string;
  institution_or_hostel_name: string;
  room_number?: string | null;
  role: Role;
  approval_status: ApprovalStatus;
  created_at: string;
  updated_at: string;
};

export type MealStat = {
  menu_items: string[];
  custom_question: CustomQuestion;
  eating_count: number;
  not_eating_count: number;
  like_count: number;
  dislike_count: number;
  like_pct: number | null;
  dislike_pct: number | null;
  item_counts: { item_name: string; count: number }[];
  reason_counts: { reason: string; count: number }[];
  custom_answer_counts: { answer: string; count: number }[];
};

export type AdminTodayResponse = {
  date: string;
  day: string;
  total_responses: number;
  breakfast: MealStat;
  lunch: MealStat;
  dinner: MealStat;
};

export type DashboardItem = {
  item_name: string;
  preference_count: number;
  quantity_per_person: number | null;
  unit: Unit | null;
  suggested: number | null;
  display: { value: number; unit: string } | null;
};

export type DashboardMeal = {
  menu_items: string[];
  eating_count: number;
  not_eating_count: number;
  items: DashboardItem[];
  warnings: string[];
};

export type DashboardResponse = {
  date: string;
  day: string;
  meals: { breakfast: DashboardMeal; lunch: DashboardMeal; dinner: DashboardMeal };
  summary: {
    breakfast_eating: number;
    lunch_eating: number;
    dinner_eating: number;
    total_responses: number;
    most_demanded: { item: string; count: number } | null;
    least_demanded: { item: string; count: number } | null;
  };
};

export type NecessaryItem = {
  id: string;
  item_name: string;
  meal_type: MealType;
  quantity_per_person: number;
  unit: Unit;
  price_per_unit: number;
  price_unit: Unit;
  updated_at?: string;
};

export type WastageDocFull = {
  id: string;
  date: string;
  breakfast_items: any[];
  lunch_items: any[];
  dinner_items: any[];
  breakfast_wastage_kg: number;
  lunch_wastage_kg: number;
  dinner_wastage_kg: number;
  breakfast_loss?: number;
  lunch_loss?: number;
  dinner_loss?: number;
  total_loss?: number;
  manual_total_cost?: number | null;
  item_loss_total?: number;
};

export type AdminWastageToday = {
  date: string;
  today: WastageDocFull | null;
  yesterday: WastageDocFull | null;
  last_week_same_day: WastageDocFull | null;
  average_loss_30d: number | null;
  saved_amount_vs_avg: number | null;
};

export type AdminWastageTrend = {
  range: number;
  meal: "all" | MealType;
  wastage_series: { date: string; value: number }[];
  saved_series: { date: string; value: number }[];
};

export type AppSettings = {
  id: string;
  default_meal_state: "ON" | "OFF";
  default_like_dislike_state: Reaction;
  default_preference_state: "none" | "all" | "previous";
  notifications_enabled: boolean;
  language: string;
  updated_at?: string;
};

async function request<T>(
  path: string,
  options: { method?: string; body?: any; token?: string | null } = {},
): Promise<T> {
  const { method = "GET", body, token } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return data as T;
}

export const api = {
  // Auth
  registerStudent: (payload: {
    full_name: string;
    mobile_or_user_id: string;
    institution_or_hostel_name: string;
    room_number: string;
    password: string;
  }) => request<User>("/auth/register-student", { method: "POST", body: payload }),
  login: (payload: {
    mobile_or_user_id: string;
    password: string;
    institution_or_hostel_name: string;
  }) =>
    request<{
      challenge: string;
      delivery: "sms" | "dev";
      dev_otp: string | null;
      masked_mobile: string;
      user_preview: {
        full_name: string;
        role: Role;
        mobile_or_user_id: string;
        institution_or_hostel_name: string;
      };
    }>("/auth/login", { method: "POST", body: payload }),
  verifyLoginOtp: (payload: { challenge: string; otp: string }) =>
    request<TokenResponse>("/auth/verify-login-otp", {
      method: "POST",
      body: payload,
    }),
  resendOtp: (payload: { challenge: string }) =>
    request<{ delivery: "sms" | "dev"; dev_otp: string | null; masked_mobile: string }>(
      "/auth/resend-otp",
      { method: "POST", body: payload },
    ),
  savePushToken: (
    token: string,
    payload: { push_token: string; platform?: "ios" | "android" | "web" },
  ) =>
    request<{ ok: boolean }>("/auth/push-token", {
      method: "POST",
      body: payload,
      token,
    }),
  registerPush: (
    token: string,
    payload: { user_id: string; platform: "ios" | "android" | "web"; device_token: string },
  ) =>
    request<{ status: string }>("/register-push", {
      method: "POST",
      body: payload,
      token,
    }),
  me: (token: string) => request<User>("/auth/me", { token }),

  // Student
  studentMeta: (token: string) =>
    request<{ reasons: string[]; days: string[] }>("/student/meta", { token }),
  studentToday: (token: string) => request<TodayResponse>("/student/today", { token }),
  upsertToday: (
    token: string,
    body: {
      breakfast: Partial<MealPlan>;
      lunch: Partial<MealPlan>;
      dinner: Partial<MealPlan>;
    },
  ) =>
    request<{ ok: boolean; plan: TodayResponse["plan"] }>("/student/today", {
      method: "PUT",
      body,
      token,
    }),
  postFeedback: (token: string, feedback_text: string) =>
    request<{ ok: boolean; id: string; created_at: string }>("/student/feedback", {
      method: "POST",
      body: { feedback_text },
      token,
    }),
  menuWeek: (token: string) =>
    request<{ days: WeeklyDay[] }>("/student/menu/week", { token }),
  menuMonth: (token: string) =>
    request<{ weeks: { label: string; days: WeeklyDay[] }[] }>("/student/menu/month", {
      token,
    }),
  setReaction: (
    token: string,
    body: { day: string; meal_type: MealType; reaction: Reaction },
  ) =>
    request<{ ok: boolean; reaction: Reaction }>("/student/menu/reaction", {
      method: "PUT",
      body,
      token,
    }),
  wastage: (token: string, range: 7 | 30 | 90, meal: "all" | MealType) =>
    request<WastageResponse>(`/student/wastage?range=${range}&meal=${meal}`, { token }),

  // Admin
  adminStudentsSummary: (token: string) =>
    request<StudentsSummary>("/admin/students/summary", { token }),
  adminStudentsList: (
    token: string,
    status: "all" | "pending" | "approved" | "blocked" = "all",
  ) =>
    request<{ students: StudentRow[]; count: number }>(
      `/admin/students?status=${status}`,
      { token },
    ),
  adminApprove: (token: string, id: string) =>
    request<{ ok: boolean }>(`/admin/students/${id}/approve`, {
      method: "POST",
      token,
    }),
  adminReject: (token: string, id: string) =>
    request<{ ok: boolean }>(`/admin/students/${id}/reject`, {
      method: "POST",
      token,
    }),
  adminToday: (token: string) =>
    request<AdminTodayResponse>("/admin/today", { token }),
  adminFeedback: (token: string, days: number = 7) =>
    request<{
      items: { id: string; date: string; feedback_text: string; created_at: string }[];
      count: number;
    }>(`/admin/feedback?days=${days}`, { token }),
  adminDashboard: (token: string) =>
    request<DashboardResponse>("/admin/dashboard", { token }),

  adminNecessaryInfo: (token: string) =>
    request<{ items: NecessaryItem[]; count: number }>("/admin/necessary-info", {
      token,
    }),
  adminNiCreate: (token: string, body: Omit<NecessaryItem, "id" | "updated_at">) =>
    request<NecessaryItem>("/admin/necessary-info", {
      method: "POST",
      body,
      token,
    }),
  adminNiUpdate: (
    token: string,
    id: string,
    body: Omit<NecessaryItem, "id" | "updated_at">,
  ) =>
    request<NecessaryItem>(`/admin/necessary-info/${id}`, {
      method: "PUT",
      body,
      token,
    }),
  adminNiDelete: (token: string, id: string) =>
    request<{ ok: boolean }>(`/admin/necessary-info/${id}`, {
      method: "DELETE",
      token,
    }),

  adminMenuList: (token: string) =>
    request<{ days: DailyMenu[] }>("/admin/menus", { token }),
  adminMenuUpsert: (
    token: string,
    day: string,
    body: {
      breakfast_items: string[];
      lunch_items: string[];
      dinner_items: string[];
      breakfast_custom_question: CustomQuestion;
      lunch_custom_question: CustomQuestion;
      dinner_custom_question: CustomQuestion;
    },
  ) => request<DailyMenu>(`/admin/menus/${day}`, { method: "PUT", body, token }),

  adminWastageToday: (token: string) =>
    request<AdminWastageToday>("/admin/wastage/today", { token }),
  adminWastageTrend: (
    token: string,
    range: 7 | 30 | 90,
    meal: "all" | MealType,
  ) =>
    request<AdminWastageTrend>(
      `/admin/wastage/trend?range=${range}&meal=${meal}`,
      { token },
    ),
  adminWastageUpsert: (
    token: string,
    target_date: string,
    body: {
      breakfast_items: { item_name: string; quantity: number; unit: Unit }[];
      lunch_items: { item_name: string; quantity: number; unit: Unit }[];
      dinner_items: { item_name: string; quantity: number; unit: Unit }[];
      manual_total_cost?: number;
    },
  ) =>
    request<{ ok: boolean; wastage: WastageDocFull }>(
      `/admin/wastage/${target_date}`,
      { method: "PUT", body, token },
    ),

  adminSettings: (token: string) =>
    request<AppSettings>("/admin/settings", { token }),
  adminSettingsUpdate: (token: string, body: Partial<AppSettings>) =>
    request<AppSettings>("/admin/settings", { method: "PUT", body, token }),

  // Notifications
  studentNotifications: (token: string) =>
    request<{
      items: {
        id: string;
        title: string;
        body: string;
        type: string;
        scheduled_for: string;
        created_at: string;
        read: boolean;
      }[];
      unread_count: number;
    }>("/student/notifications", { token }),
  markNotifRead: (token: string, id: string) =>
    request<{ ok: boolean }>(`/student/notifications/${id}/read`, {
      method: "POST",
      token,
    }),
  adminNotifications: (token: string) =>
    request<{
      items: {
        id: string;
        title: string;
        body: string;
        type: string;
        scheduled_for: string;
        created_at: string;
      }[];
    }>("/admin/notifications", { token }),
  adminCreateNotification: (
    token: string,
    body: {
      title: string;
      body: string;
      audience?: "all" | "student";
      recipient_id?: string;
      type?: "announcement" | "menu_reminder" | "system";
      scheduled_for?: string;
    },
  ) =>
    request<any>("/admin/notifications", {
      method: "POST",
      body,
      token,
    }),
  adminMenuReminder: (token: string, custom_body?: string) =>
    request<any>("/admin/notifications/menu-reminder", {
      method: "POST",
      body: { custom_body },
      token,
    }),
  adminDispatchReminder: (
    token: string,
    payload: { audience?: "student" | "admin" | "all"; title?: string; body?: string },
  ) =>
    request<{
      ok: boolean;
      audience: string;
      recipients: number;
      notification: any;
    }>("/admin/notifications/dispatch-reminder", {
      method: "POST",
      body: payload,
      token,
    }),
};
