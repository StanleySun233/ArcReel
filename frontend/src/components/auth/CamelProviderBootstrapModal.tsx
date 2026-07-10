import { useEffect, useId, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ExternalLink, KeyRound, Loader2, RefreshCcw } from "lucide-react";
import {
  API,
  type CamelBootstrapProviderPreview,
  type CamelBootstrapResult,
  type CamelBootstrapStatus,
  type CamelBootstrapTokenLink,
} from "@/api";
import { useAuthStore } from "@/stores/auth-store";
import { useConfigStatusStore } from "@/stores/config-status-store";
import { GlassModal } from "@/components/ui/GlassModal";
import { ModalCloseButton } from "@/components/ui/ModalCloseButton";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";

function currentReturnPath(): string {
  return window.location.pathname + window.location.search + window.location.hash;
}

function consumeBootstrapResult(): CamelBootstrapResult | null {
  const url = new URL(window.location.href);
  const raw = url.searchParams.get("camel_bootstrap_result");
  if (!raw) return null;
  url.searchParams.delete("camel_bootstrap");
  url.searchParams.delete("camel_bootstrap_result");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  return JSON.parse(raw) as CamelBootstrapResult;
}

function tokenLinks(result: CamelBootstrapResult | null): CamelBootstrapTokenLink[] {
  if (!result || result.completed) return [];
  if (result.error === "camel_token_conflict" && "conflicts" in result) return result.conflicts ?? [];
  if (result.error === "partial_bootstrap_failed" && "created_tokens" in result) return result.created_tokens ?? [];
  return [];
}

function ProviderRows({ providers }: { providers: CamelBootstrapProviderPreview[] }) {
  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-hairline-soft">
      {providers.map((provider) => (
        <div key={provider.media} className="grid gap-1 border-b border-hairline-soft px-3 py-2 last:border-b-0">
          <div className="flex items-center justify-between gap-3 text-[12px] text-text-2">
            <span className="font-medium text-text">{provider.provider_name}</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-4">{provider.media}</span>
          </div>
          <div className="break-all font-mono text-[11px] text-text-3">{provider.token_name}</div>
          <div className="text-[11px] text-text-4">
            {provider.endpoint} - {provider.models.join(", ")}
          </div>
        </div>
      ))}
    </div>
  );
}

function TokenLinks({ links }: { links: CamelBootstrapTokenLink[] }) {
  if (links.length === 0) return null;
  return (
    <div className="mt-4 space-y-2">
      {links.map((link) => (
        <a
          key={`${link.media}:${link.token_name}`}
          href={link.delete_url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between gap-3 rounded-lg border border-hairline-soft bg-bg-grad-a/45 px-3 py-2 text-[12px] text-text-2 transition-colors hover:border-hairline hover:text-text"
        >
          <span className="min-w-0">
            <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-text-4">{link.media}</span>
            <span className="block break-all">{link.token_name}</span>
          </span>
          <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden />
        </a>
      ))}
    </div>
  );
}

export function CamelProviderBootstrapModal() {
  const titleId = useId();
  const descId = useId();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const authMode = useAuthStore((s) => s.authMode);
  const [status, setStatus] = useState<CamelBootstrapStatus | null>(null);
  const [result, setResult] = useState<CamelBootstrapResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || authMode !== "camel") return;
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setLoadError(null);
      setDismissed(false);
      try {
        setResult(consumeBootstrapResult());
      } catch {
        setResult({ completed: false, error: "failed" });
      }
      try {
        const nextStatus = await API.getCamelBootstrapStatus();
        if (!cancelled) setStatus(nextStatus);
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authMode, isAuthenticated]);

  useEffect(() => {
    if (result?.completed) {
      void useConfigStatusStore.getState().refresh();
    }
  }, [result]);

  const links = useMemo(() => tokenLinks(result), [result]);
  const open = authMode === "camel" && isAuthenticated && !dismissed && Boolean(result || status?.needed || loadError);
  const isSuccess = result?.completed === true;
  const isConflict = result?.completed === false && result.error === "camel_token_conflict";
  const isPartial = result?.completed === false && result.error === "partial_bootstrap_failed";
  const isTokenError = result?.completed === false && result.error === "camel_token_error";
  const canStart = status?.needed === true || isConflict || isPartial;

  if (!open) return null;

  const start = async () => {
    setStarting(true);
    setLoadError(null);
    try {
      const response = await API.startCamelBootstrap("create", currentReturnPath());
      window.location.assign(response.authorization_url);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
      setStarting(false);
    }
  };
  const dismiss = () => {
    setResult(null);
    setDismissed(true);
  };

  return (
    <GlassModal
      open={open}
      onClose={dismiss}
      labelledBy={titleId}
      describedBy={descId}
      widthClassName="w-[min(520px,calc(100vw-32px))]"
      closeOnBackdrop={isSuccess}
    >
      <div className="px-6 pb-6 pt-5">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-hairline-soft bg-bg-grad-a/55 text-accent-2">
            {isSuccess ? <CheckCircle2 className="h-5 w-5" aria-hidden /> : <KeyRound className="h-5 w-5" aria-hidden />}
          </span>
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="display-serif text-[18px] font-semibold tracking-tight text-text">
              {isSuccess ? "CaMeL providers are ready" : "Set up CaMeL providers"}
            </h2>
            <p id={descId} className="mt-1 text-[12.5px] leading-relaxed text-text-3">
              ArcReel will create four CaMeL API keys named camel-arcreel-{"{camel_user_id}"}-image, text, video, and audio, then configure four ArcReel custom providers for this user. Raw keys stay on the server.
            </p>
          </div>
          <ModalCloseButton onClick={dismiss} />
        </div>

        {loading && (
          <div className="mt-5 flex items-center gap-2 text-[12.5px] text-text-3">
            <Loader2 className="h-3.5 w-3.5 motion-safe:animate-spin" aria-hidden />
            Checking CaMeL provider status...
          </div>
        )}

        {loadError && (
          <div className="mt-5 flex items-start gap-2 rounded-lg border border-warm-ring bg-warm-tint px-3 py-2 text-[12px] text-warm-bright" role="alert">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            <span>{loadError}</span>
          </div>
        )}

        {status?.needed && <ProviderRows providers={status.providers} />}

        {isSuccess && (
          <div className="mt-5 rounded-lg border border-hairline-soft bg-bg-grad-a/45 px-3 py-2 text-[12.5px] text-text-2">
            Bootstrap completed. Provider configuration is refreshing.
          </div>
        )}

        {(isConflict || isPartial) && (
          <div className="mt-5 rounded-lg border border-warm-ring bg-warm-tint px-3 py-2 text-[12.5px] leading-relaxed text-warm-bright" role="alert">
            {isConflict
              ? "CaMeL already has tokens with these names. Delete them in CaMeL, then retry."
              : "CaMeL tokens were created, but ArcReel provider setup did not complete. Delete these tokens, then retry."}
          </div>
        )}

        {isTokenError && (
          <div className="mt-5 rounded-lg border border-warm-ring bg-warm-tint px-3 py-2 text-[12.5px] leading-relaxed text-warm-bright" role="alert">
            CaMeL token setup failed{result.message ? `: ${result.message}` : "."}
          </div>
        )}

        <TokenLinks links={links} />

        <div className="mt-6 flex justify-end gap-2">
          {isSuccess ? (
            <PrimaryButton size="sm" onClick={dismiss}>
              Done
            </PrimaryButton>
          ) : (
            <>
              <SecondaryButton size="sm" onClick={dismiss}>
                Later
              </SecondaryButton>
              <PrimaryButton
                size="sm"
                onClick={() => void start()}
                disabled={!canStart || starting}
                leadingIcon={isConflict || isPartial ? <RefreshCcw className="h-3.5 w-3.5" aria-hidden /> : undefined}
              >
                {starting ? "Starting..." : isConflict || isPartial ? "Retry setup" : "Start setup"}
              </PrimaryButton>
            </>
          )}
        </div>
      </div>
    </GlassModal>
  );
}
