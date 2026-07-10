import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenantSwitcher } from "@/components/tenant/TenantSwitcher";
import { useAuthStore } from "@/stores/auth-store";

const personalTenant = {
  id: "ten_personal",
  name: "Alice Personal",
  role: "admin" as const,
  is_owner: true,
  personal: true,
};

const teamTenant = {
  id: "ten_team",
  name: "Studio Team",
  role: "member" as const,
  is_owner: false,
  personal: false,
};

function jsonResponse(jsonData: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: vi.fn().mockResolvedValue(jsonData),
  } as unknown as Response;
}

describe("TenantSwitcher", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    useAuthStore.setState(useAuthStore.getInitialState(), true);
    useAuthStore.setState({
      token: "personal-token",
      username: "alice",
      isAuthenticated: true,
      currentTenant: personalTenant,
      tenants: [personalTenant, teamTenant],
      tenantRole: "admin",
      isTenantOwner: true,
    });
  });

  it("opens a tenant listbox and switches tenant through the auth store", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        access_token: "team-token",
        token_type: "bearer",
        tenant: teamTenant,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<TenantSwitcher />);

    fireEvent.click(screen.getByRole("button", { name: /Alice Personal/ }));

    expect(screen.getByRole("listbox", { name: "切换空间" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: /Studio Team/ }));

    await waitFor(() => {
      expect(useAuthStore.getState()).toMatchObject({
        token: "team-token",
        currentTenant: teamTenant,
        tenantRole: "member",
      });
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/tenant-token",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ tenant_id: "ten_team" }),
      }),
    );
  });
});
