import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { TenantPermissionGate } from "@/components/tenant/TenantPermissionGate";
import { useAuthStore } from "@/stores/auth-store";

describe("TenantPermissionGate", () => {
  beforeEach(() => {
    useAuthStore.setState(useAuthStore.getInitialState(), true);
  });

  it("hides write actions from view-only users", () => {
    useAuthStore.setState({ tenantRole: "view", isTenantOwner: false });

    render(
      <TenantPermissionGate permission="write">
        <button type="button">Create project</button>
      </TenantPermissionGate>,
    );

    expect(screen.queryByRole("button", { name: "Create project" })).not.toBeInTheDocument();
  });

  it("shows write actions to members", () => {
    useAuthStore.setState({ tenantRole: "member", isTenantOwner: false });

    render(
      <TenantPermissionGate permission="write">
        <button type="button">Create project</button>
      </TenantPermissionGate>,
    );

    expect(screen.getByRole("button", { name: "Create project" })).toBeInTheDocument();
  });

  it("hides tenant admin actions from non-admin users", () => {
    useAuthStore.setState({ tenantRole: "member", isTenantOwner: false });

    render(
      <TenantPermissionGate permission="tenant_admin">
        <button type="button">Invite member</button>
      </TenantPermissionGate>,
    );

    expect(screen.queryByRole("button", { name: "Invite member" })).not.toBeInTheDocument();
  });

  it("hides admin promotion from non-owner admins", () => {
    useAuthStore.setState({ tenantRole: "admin", isTenantOwner: false });

    render(
      <TenantPermissionGate permission="admin_promotion">
        <button type="button">Promote admin</button>
      </TenantPermissionGate>,
    );

    expect(screen.queryByRole("button", { name: "Promote admin" })).not.toBeInTheDocument();
  });

  it("shows admin promotion to owners", () => {
    useAuthStore.setState({ tenantRole: "admin", isTenantOwner: true });

    render(
      <TenantPermissionGate permission="admin_promotion">
        <button type="button">Promote admin</button>
      </TenantPermissionGate>,
    );

    expect(screen.getByRole("button", { name: "Promote admin" })).toBeInTheDocument();
  });
});
