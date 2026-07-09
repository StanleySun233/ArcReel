import { useState } from "react";
import { KeyRound, Loader2, RefreshCcw } from "lucide-react";
import { API } from "@/api";
import { PrimaryButton } from "@/components/ui/PrimaryButton";

function accountReturnPath(): string {
  return "/app/settings?section=account";
}

export function CamelAccountSection() {
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const repair = async () => {
    setStarting(true);
    setError(null);
    try {
      const response = await API.startCamelBootstrap("repair", accountReturnPath());
      window.location.assign(response.authorization_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStarting(false);
    }
  };

  return (
    <section className="space-y-5">
      <div>
        <div className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-accent-2">
          CaMeL
        </div>
        <h2 className="font-editorial mt-1 text-[22px] font-medium text-text">Account</h2>
      </div>

      <div className="rounded-[8px] border border-hairline-soft bg-bg-grad-a/45 p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[13px] font-medium text-text">
              <KeyRound className="h-4 w-4 text-accent-2" aria-hidden />
              CaMeL provider keys
            </div>
            <p className="mt-1 text-[12.5px] leading-relaxed text-text-3">
              Re-authorize with CaMeL and repair the ArcReel-managed image, text, video, and audio provider keys.
            </p>
          </div>
          <PrimaryButton
            size="sm"
            onClick={() => void repair()}
            disabled={starting}
            leadingIcon={
              starting ? (
                <Loader2 className="h-3.5 w-3.5 motion-safe:animate-spin" aria-hidden />
              ) : (
                <RefreshCcw className="h-3.5 w-3.5" aria-hidden />
              )
            }
          >
            {starting ? "Starting..." : "Repair keys"}
          </PrimaryButton>
        </div>
        {error && (
          <div className="mt-4 rounded-[8px] border border-warm-ring bg-warm-tint px-3 py-2 text-[12px] text-warm-bright" role="alert">
            {error}
          </div>
        )}
      </div>
    </section>
  );
}
