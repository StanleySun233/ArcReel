import type { ReactNode } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { canManageTenant, canPromoteTenantAdmin, canWriteTenant } from "@/utils/auth";

export type TenantPermission = "write" | "tenant_admin" | "admin_promotion";

interface TenantPermissionGateProps {
  permission: TenantPermission;
  children: ReactNode;
  fallback?: ReactNode;
}

export function TenantPermissionGate({
  permission,
  children,
  fallback = null,
}: TenantPermissionGateProps) {
  const tenantRole = useAuthStore((state) => state.tenantRole);
  const isTenantOwner = useAuthStore((state) => state.isTenantOwner);

  const allowed = permission === "write"
    ? canWriteTenant(tenantRole)
    : permission === "tenant_admin"
      ? canManageTenant(tenantRole)
      : canPromoteTenantAdmin(isTenantOwner);

  return allowed ? children : fallback;
}
