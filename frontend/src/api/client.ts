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
    institution_or_hostel_name?: string;
  }) => request<TokenResponse>("/auth/login", { method: "POST", body: payload }),

  me: (token: string) => request<User>("/auth/me", { token }),

  // Student
  studentMeta: (token: string) =>
    request<{ reasons: string[]; days: string[] }>("/student/meta", { token }),

  studentToday: (token: string) =>
    request<TodayResponse>("/student/today", { token }),

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

  wastage: (
    token: string,
    range: 7 | 30 | 90,
    meal: "all" | MealType,
  ) =>
    request<WastageResponse>(`/student/wastage?range=${range}&meal=${meal}`, {
      token,
    }),
};
