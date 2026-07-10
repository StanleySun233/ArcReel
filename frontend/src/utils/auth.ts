const TOKEN_KEY = "arcreel_auth_token";
const TENANT_SESSION_KEY = "arcreel_tenant_session";

export type TenantRole = "admin" | "member" | "view";

export interface AuthTenant {
  id: string;
  name: string;
  role: TenantRole;
  is_owner: boolean;
  personal: boolean;
}

export interface TenantSessionSnapshot {
  currentTenant: AuthTenant | null;
  tenants: AuthTenant[];
}

export type TenantAccessRecoveryReason = "stale_role" | "access_revoked";

type TenantAccessRecoveryHandler = (
  reason: TenantAccessRecoveryReason,
  fallbackTenantId?: string,
) => Promise<boolean>;

let tenantAccessRecoveryHandler: TenantAccessRecoveryHandler | null = null;

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function getAuthHeader(): string | null {
  const token = getToken();
  return token ? `Bearer ${token}` : null;
}

export function getTenantSession(): TenantSessionSnapshot {
  const raw = localStorage.getItem(TENANT_SESSION_KEY);
  if (!raw) return { currentTenant: null, tenants: [] };
  const parsed = JSON.parse(raw) as { version?: number } & TenantSessionSnapshot;
  return parsed.version === 1
    ? { currentTenant: parsed.currentTenant, tenants: parsed.tenants }
    : { currentTenant: null, tenants: [] };
}

export function setTenantSession(snapshot: TenantSessionSnapshot): void {
  localStorage.setItem(TENANT_SESSION_KEY, JSON.stringify({ version: 1, ...snapshot }));
}

export function clearTenantSession(): void {
  localStorage.removeItem(TENANT_SESSION_KEY);
}

export function setTenantAccessRecoveryHandler(handler: TenantAccessRecoveryHandler): void {
  tenantAccessRecoveryHandler = handler;
}

export async function recoverTenantAccess(
  reason: TenantAccessRecoveryReason,
  fallbackTenantId?: string,
): Promise<boolean> {
  return tenantAccessRecoveryHandler ? tenantAccessRecoveryHandler(reason, fallbackTenantId) : false;
}

export function canWriteTenant(role: TenantRole | null): boolean {
  return role === "admin" || role === "member";
}

export function canManageTenant(role: TenantRole | null): boolean {
  return role === "admin";
}

export function canPromoteTenantAdmin(isOwner: boolean): boolean {
  return isOwner;
}
