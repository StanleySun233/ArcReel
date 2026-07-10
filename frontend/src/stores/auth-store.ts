import { create } from "zustand";
import {
  clearTenantSession,
  clearToken,
  getTenantSession,
  getToken,
  setTenantAccessRecoveryHandler,
  setTenantSession,
  setToken as saveToken,
  type AuthTenant,
  type TenantRole,
} from "@/utils/auth";

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

export interface AuthState {
  token: string | null;
  username: string | null;
  currentTenant: AuthTenant | null;
  tenants: AuthTenant[];
  tenantRole: TenantRole | null;
  isTenantOwner: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  authStatus: AuthStatus | null;
  authMode: AuthMode;
  providers: AuthProvider[];
  initialize: () => void;
  login: (token: string, username: string) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
  switchTenant: (tenantId: string) => Promise<void>;
  refreshCurrentTenant: () => Promise<boolean>;
  fallbackToPersonalTenant: (fallbackTenantId?: string) => Promise<boolean>;
}

interface AuthMeResponse {
  tenant: AuthTenant;
}

interface AuthTenantsResponse {
  tenants: AuthTenant[];
}

interface TenantTokenResponse {
  access_token: string;
  tenant: AuthTenant;
}

class AuthRequestError extends Error {
  constructor(readonly response: Response) {
    super(`auth request failed: ${response.status}`);
  }
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

function authHeaders(token: string): Headers {
  const headers = new Headers({ "Content-Type": "application/json" });
  headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

async function fetchJson<T>(url: string, token: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...init, headers: authHeaders(token) });
  if (!response.ok) {
    throw new AuthRequestError(response);
  }
  return response.json() as Promise<T>;
}

function tenantFields(currentTenant: AuthTenant | null, tenants: AuthTenant[]) {
  return {
    currentTenant,
    tenants,
    tenantRole: currentTenant?.role ?? null,
    isTenantOwner: currentTenant?.is_owner ?? false,
  };
}

function persistTenantFields(currentTenant: AuthTenant | null, tenants: AuthTenant[]) {
  setTenantSession({ currentTenant, tenants });
  return tenantFields(currentTenant, tenants);
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  username: null,
  currentTenant: null,
  tenants: [],
  tenantRole: null,
  isTenantOwner: false,
  isAuthenticated: false,
  isLoading: true,
  authStatus: null,
  authMode: "local",
  providers: [],

  initialize: () => {
    const token = getToken();
    const tenantSession = getTenantSession();
    if (token) {
      set({
        token,
        isAuthenticated: true,
        isLoading: false,
        ...tenantFields(tenantSession.currentTenant, tenantSession.tenants),
      });
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
    Promise.all([
      fetchJson<AuthMeResponse>("/api/v1/auth/me", token),
      fetchJson<AuthTenantsResponse>("/api/v1/auth/tenants", token),
    ])
      .then(([me, tenants]) => {
        set(persistTenantFields(me.tenant, tenants.tenants));
      })
      .catch(() => {});
  },

  logout: () => {
    clearToken();
    clearTenantSession();
    set({
      token: null,
      username: null,
      currentTenant: null,
      tenants: [],
      tenantRole: null,
      isTenantOwner: false,
      isAuthenticated: false,
    });
  },

  setLoading: (isLoading) => set({ isLoading }),

  switchTenant: async (tenantId) => {
    const token = get().token ?? getToken();
    if (!token) return;
    const payload = await fetchJson<TenantTokenResponse>("/api/v1/auth/tenant-token", token, {
      method: "POST",
      body: JSON.stringify({ tenant_id: tenantId }),
    });
    saveToken(payload.access_token);
    set((state) => {
      const tenants = state.tenants.map((tenant) => (
        tenant.id === payload.tenant.id ? payload.tenant : tenant
      ));
      return {
        token: payload.access_token,
        ...persistTenantFields(payload.tenant, tenants),
      };
    });
  },

  refreshCurrentTenant: async () => {
    const token = get().token ?? getToken();
    if (!token) return false;
    try {
      const payload = await fetchJson<TenantTokenResponse>("/api/v1/auth/refresh-current-tenant", token, {
        method: "POST",
      });
      saveToken(payload.access_token);
      set((state) => ({
        token: payload.access_token,
        ...persistTenantFields(
          payload.tenant,
          state.tenants.map((tenant) => (tenant.id === payload.tenant.id ? payload.tenant : tenant)),
        ),
      }));
      return true;
    } catch (error) {
      if (!(error instanceof AuthRequestError) || error.response.status !== 403) return false;
      const payload = await error.response.json().catch(() => ({})) as { error?: string; fallback_tenant_id?: string };
      return payload.error === "TENANT_ACCESS_REVOKED"
        ? get().fallbackToPersonalTenant(payload.fallback_tenant_id)
        : false;
    }
  },

  fallbackToPersonalTenant: async (fallbackTenantId) => {
    const targetTenantId = fallbackTenantId ?? get().tenants.find((tenant) => tenant.personal)?.id;
    if (!targetTenantId) return false;
    await get().switchTenant(targetTenantId);
    return true;
  },
}));

setTenantAccessRecoveryHandler((reason, fallbackTenantId) => {
  return reason === "stale_role"
    ? useAuthStore.getState().refreshCurrentTenant()
    : useAuthStore.getState().fallbackToPersonalTenant(fallbackTenantId);
});
