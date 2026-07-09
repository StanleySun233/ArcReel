import { create } from "zustand";
import { getToken, setToken as saveToken, clearToken } from "@/utils/auth";

export type AuthMode = "local" | "camel";

export interface AuthProvider {
  id: string;
  label: string;
  login_url: string;
}

export interface AuthStatus {
  enabled: boolean;
  mode: AuthMode;
  providers: AuthProvider[];
}

interface AuthState {
  token: string | null;
  username: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authStatus: AuthStatus | null;
  authMode: AuthMode;
  providers: AuthProvider[];
  initialize: () => void;
  login: (token: string, username: string) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
}

function parseAuthStatus(payload: unknown): AuthStatus {
  if (
    typeof payload !== "object" ||
    payload === null ||
    typeof (payload as { enabled?: unknown }).enabled !== "boolean"
  ) {
    throw new Error("invalid /auth/status payload");
  }

  const data = payload as { enabled: boolean; mode?: unknown; providers?: unknown };
  const providers = Array.isArray(data.providers)
    ? data.providers.filter((provider): provider is AuthProvider => {
        if (typeof provider !== "object" || provider === null) return false;
        const item = provider as Partial<Record<keyof AuthProvider, unknown>>;
        return (
          typeof item.id === "string" &&
          typeof item.label === "string" &&
          typeof item.login_url === "string"
        );
      })
    : [];

  return {
    enabled: data.enabled,
    mode: data.mode === "camel" ? "camel" : "local",
    providers,
  };
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  username: null,
  isAuthenticated: false,
  isLoading: true,
  authStatus: null,
  authMode: "local",
  providers: [],

  initialize: () => {
    const token = getToken();
    if (token) {
      set({ token, isAuthenticated: true, isLoading: false });
    } else {
      set({ isLoading: true });
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    fetch("/api/v1/auth/status", { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`status ${res.status}`);
        const status = parseAuthStatus(await res.json());
        set({ authStatus: status, authMode: status.mode, providers: status.providers });
        if (!status.enabled) {
          set({ isAuthenticated: true });
        }
      })
      .catch((err) => {
        console.warn("[auth] /auth/status fetch failed; defaulting to login", err);
      })
      .finally(() => {
        clearTimeout(timeoutId);
        if (!token) {
          set({ isLoading: false });
        }
      });
  },

  login: (token, username) => {
    saveToken(token);
    set({ token, username, isAuthenticated: true, isLoading: false });
  },

  logout: () => {
    clearToken();
    set({ token: null, username: null, isAuthenticated: false });
  },

  setLoading: (isLoading) => set({ isLoading }),
}));
