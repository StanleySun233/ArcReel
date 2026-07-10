import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/stores/auth-store";

export function TenantSwitcher() {
  const { t } = useTranslation("auth");
  const currentTenant = useAuthStore((state) => state.currentTenant);
  const tenants = useAuthStore((state) => state.tenants);
  const switchTenant = useAuthStore((state) => state.switchTenant);
  const [open, setOpen] = useState(false);
  const [pendingTenantId, setPendingTenantId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const handleSelect = useCallback(
    async (tenantId: string) => {
      if (tenantId === currentTenant?.id) {
        setOpen(false);
        return;
      }
      setError("");
      setPendingTenantId(tenantId);
      try {
        await switchTenant(tenantId);
        setOpen(false);
      } catch {
        setError(t("tenant_switch_failed"));
      } finally {
        setPendingTenantId(null);
      }
    },
    [currentTenant?.id, switchTenant, t],
  );

  if (!currentTenant || tenants.length === 0) return null;

  return (
    <div className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`${t("tenant_switcher_label")}: ${currentTenant.name}`}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex max-w-64 items-center gap-2 rounded-full border border-hairline bg-surface-2 px-3 py-1.5 text-sm text-text shadow-sm hover:border-accent/50"
      >
        <span className="truncate">{currentTenant.name}</span>
        <span className="rounded-full bg-surface-3 px-2 py-0.5 text-xs text-text-3">
          {t(`tenant_role_${currentTenant.role}`)}
        </span>
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label={t("tenant_switcher_label")}
          className="absolute right-0 z-50 mt-2 w-72 overflow-hidden rounded-xl border border-hairline bg-surface shadow-xl"
        >
          {tenants.map((tenant) => {
            const selected = tenant.id === currentTenant.id;
            const pending = pendingTenantId === tenant.id;
            return (
              <li
                key={tenant.id}
                role="option"
                aria-selected={selected}
                aria-disabled={pending || undefined}
                tabIndex={0}
                onClick={() => void handleSelect(tenant.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    void handleSelect(tenant.id);
                  }
                }}
                className={`cursor-pointer px-3 py-2 text-sm outline-none hover:bg-surface-2 focus:bg-surface-2 ${
                  selected ? "bg-surface-2 text-text" : "text-text-2"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate">{tenant.name}</span>
                  <span className="shrink-0 text-xs text-text-4">
                    {pending ? t("tenant_switching") : t(`tenant_role_${tenant.role}`)}
                  </span>
                </div>
                {tenant.personal && (
                  <div className="mt-0.5 text-xs text-text-4">{t("tenant_personal_badge")}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {error && (
        <p role="alert" className="mt-2 text-xs text-warm-bright">
          {error}
        </p>
      )}
    </div>
  );
}
