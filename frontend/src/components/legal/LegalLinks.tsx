import { LEGAL_CONFIG, type LegalConfig } from "@/config/legal";

interface LegalLinksProps {
  config?: LegalConfig;
  className?: string;
}

export function LegalLinks({ config = LEGAL_CONFIG, className = "" }: LegalLinksProps) {
  return (
    <p className={`text-[12.5px] leading-[1.65] text-text-3 ${className}`}>
      Powered by {config.upstreamName} —{" "}
      <a
        href={config.upstreamUrl}
        target="_blank"
        rel="noreferrer"
        className="break-all text-accent-2 transition-colors hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        {config.upstreamUrl}
      </a>
    </p>
  );
}
