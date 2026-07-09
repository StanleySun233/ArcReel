import type { ReactNode } from "react";

import { AlertTriangle, ExternalLink } from "lucide-react";

import { LEGAL_CONFIG, type LegalConfig } from "@/config/legal";

interface LegalLinksProps {
  config?: LegalConfig;
  className?: string;
}

interface LegalAnchorProps {
  href: string;
  children: ReactNode;
}

function LegalAnchor({ href, children }: LegalAnchorProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 break-all text-accent-2 transition-colors hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
    >
      <span>{children}</span>
      <ExternalLink className="h-3 w-3 shrink-0" aria-hidden />
    </a>
  );
}

export function LegalLinks({ config = LEGAL_CONFIG, className = "" }: LegalLinksProps) {
  const sourceLabel = config.sourceRef ? `${config.sourceUrl} (${config.sourceRef})` : config.sourceUrl;

  return (
    <div className={`space-y-3 text-[12.5px] leading-[1.65] text-text-3 ${className}`}>
      {!config.sourceConfigured && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-[8px] border px-3 py-2 text-[12px]"
          style={{
            borderColor: "var(--color-warm-ring)",
            background: "var(--color-warm-tint)",
            color: "var(--color-warm-bright)",
          }}
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            Legal compliance warning: the deployed source URL is not configured. Set
            VITE_ARCREEL_LEGAL_SOURCE_URL before public deployment.
          </span>
        </div>
      )}

      <div className="space-y-1">
        <p>
          Powered by {config.upstreamName} —{" "}
          <LegalAnchor href={config.upstreamUrl}>{config.upstreamUrl}</LegalAnchor>
        </p>
        <p>Copyright © 2026 Pollo3470 and ArcReel contributors</p>
        <p>
          {config.modifiedNotice} Modified date: {config.modifiedDate}.
        </p>
        <p>
          {config.deploymentName} is offered {config.serviceModel} of charge with{" "}
          {config.apiRelayName} as the API relay; no paid access or commercial API resale is
          introduced, and free access does not remove {config.license} obligations.
        </p>
        <p>{config.warrantyNotice}</p>
        <p>{config.conveyanceNotice}</p>
      </div>

      <div className="grid gap-1.5 sm:grid-cols-2">
        {config.sourceConfigured && (
          <p>
            Deployed source: <LegalAnchor href={config.sourceUrl}>{sourceLabel}</LegalAnchor>
          </p>
        )}
        {config.sourceArchiveUrl && (
          <p>
            Source archive:{" "}
            <LegalAnchor href={config.sourceArchiveUrl}>{config.sourceArchiveUrl}</LegalAnchor>
          </p>
        )}
        <p>
          License: <LegalAnchor href={config.licenseUrl}>{config.license}</LegalAnchor>
        </p>
        <p>
          NOTICE: <LegalAnchor href={config.noticeUrl}>{config.noticeUrl}</LegalAnchor>
        </p>
        <p>
          Upstream repository:{" "}
          <LegalAnchor href={config.upstreamUrl}>{config.upstreamUrl}</LegalAnchor>
        </p>
      </div>
    </div>
  );
}
