import { waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/stores/auth-store";
import type { AuthTenant } from "@/utils/auth";
import { recoverTenantAccess } from "@/utils/auth";

function jsonResponse(jsonData: unknown, options: Partial<Response> = {}): Response {
  return {
    ok: options.ok ?? true,
    status: options.status ?? 200,
    statusText: options.statusText ?? "OK",
    json: vi.fn().mockResolvedValue(jsonData),
  } as unknown as Response;
}

const personalTenant: AuthTenant = {
  id: "ten_personal",
  name: "Alice Personal",
  role: "admin",
  is_owner: true,
  personal: true,
};

const teamTenant: AuthTenant = {
  id: "ten_team",
  name: "Studio Team",
  role: "member",
  is_owner: false,
  personal: false,
};

describe("useAuthStore", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.localStorage.clear();
    useAuthStore.setState(useAuthStore.getInitialState(), true);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads camel auth mode and providers from /api/v1/auth/status", async () => {
    const providers = [
      {
        id: "camel",
        label: "CaMeL",
        login_url: "/api/v1/auth/camel/login",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        enabled: true,
        mode: "camel",
        providers,
      }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    useAuthStore.getState().initialize();

    await waitFor(() => {
      expect(useAuthStore.getState()).toMatchObject({
        authMode: "camel",
        providers,
        authStatus: {
          enabled: true,
          mode: "camel",
          providers,
        },
        isLoading: false,
      });
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/status",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("persists token, current tenant, tenant list, role and owner snapshot after login", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({
        user: { id: "camel:1", username: "alice", provider: "camel" },
        tenant: personalTenant,
      }))
      .mockResolvedValueOnce(jsonResponse({ tenants: [personalTenant, teamTenant] }))
      .mockResolvedValueOnce(jsonResponse({ enabled: true, mode: "camel", providers: [] }));
    vi.stubGlobal("fetch", fetchMock);

    useAuthStore.getState().login("personal-token", "camel");

    await waitFor(() => {
      expect(useAuthStore.getState()).toMatchObject({
        token: "personal-token",
        currentTenant: personalTenant,
        tenants: [personalTenant, teamTenant],
        tenantRole: "admin",
        isTenantOwner: true,
      });
    });

    useAuthStore.setState(useAuthStore.getInitialState(), true);
    useAuthStore.getState().initialize();

    expect(useAuthStore.getState()).toMatchObject({
      token: "personal-token",
      currentTenant: personalTenant,
      tenants: [personalTenant, teamTenant],
      tenantRole: "admin",
      isTenantOwner: true,
      isAuthenticated: true,
    });
  });

  it("switches tenant by replacing the current token", async () => {
    useAuthStore.setState({
      token: "personal-token",
      isAuthenticated: true,
      currentTenant: personalTenant,
      tenants: [personalTenant, teamTenant],
      tenantRole: "admin",
      isTenantOwner: true,
    });
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        access_token: "team-token",
        token_type: "bearer",
        tenant: teamTenant,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await useAuthStore.getState().switchTenant("ten_team");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/tenant-token",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ tenant_id: "ten_team" }),
      }),
    );
    expect(useAuthStore.getState()).toMatchObject({
      token: "team-token",
      currentTenant: teamTenant,
      tenantRole: "member",
      isTenantOwner: false,
    });
    expect(window.localStorage.getItem("arcreel_auth_token")).toBe("team-token");
  });

  it("refreshes the current tenant token after a stale role response", async () => {
    const downgradedTeam = { ...teamTenant, role: "view" };
    useAuthStore.setState({
      token: "stale-token",
      isAuthenticated: true,
      currentTenant: teamTenant,
      tenants: [personalTenant, teamTenant],
      tenantRole: "member",
      isTenantOwner: false,
    });
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        access_token: "fresh-view-token",
        token_type: "bearer",
        tenant: downgradedTeam,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(recoverTenantAccess("stale_role")).resolves.toBe(true);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/refresh-current-tenant",
      expect.objectContaining({ method: "POST" }),
    );
    expect(useAuthStore.getState()).toMatchObject({
      token: "fresh-view-token",
      currentTenant: downgradedTeam,
      tenantRole: "view",
      isTenantOwner: false,
    });
  });

  it("falls back to personal space when current tenant access is revoked", async () => {
    useAuthStore.setState({
      token: "revoked-token",
      isAuthenticated: true,
      currentTenant: teamTenant,
      tenants: [personalTenant, teamTenant],
      tenantRole: "member",
      isTenantOwner: false,
    });
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        access_token: "personal-token-2",
        token_type: "bearer",
        tenant: personalTenant,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(recoverTenantAccess("access_revoked", "ten_personal")).resolves.toBe(true);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/tenant-token",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ tenant_id: "ten_personal" }),
      }),
    );
    expect(useAuthStore.getState()).toMatchObject({
      token: "personal-token-2",
      currentTenant: personalTenant,
      tenantRole: "admin",
      isTenantOwner: true,
    });
  });
});
