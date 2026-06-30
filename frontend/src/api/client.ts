// API client for MessMate backend.

const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

if (!BASE_URL) {
  // Fail fast at import-time so misconfig is obvious.
  console.warn("EXPO_PUBLIC_BACKEND_URL is not defined");
}

export type ApprovalStatus = "pending" | "approved" | "rejected_or_blocked";
export type Role = "student" | "admin";

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
};
