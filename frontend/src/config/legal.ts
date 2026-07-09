const env = import.meta.env as Record<string, string | undefined>;

function fromEnv(value: string | undefined, defaultValue: string): string {
  if (typeof value !== "string") return defaultValue;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : defaultValue;
}

const upstreamUrl = fromEnv(
  env.VITE_ARCREEL_LEGAL_UPSTREAM_URL,
  "https://github.com/ArcReel/ArcReel",
);
const sourceUrl = fromEnv(env.VITE_ARCREEL_LEGAL_SOURCE_URL, "");

export interface LegalConfig {
  deploymentName: string;
  serviceModel: string;
  apiRelayName: string;
  license: string;
  upstreamName: string;
  upstreamUrl: string;
  noticeText: string;
  licenseUrl: string;
  noticeUrl: string;
  sourceUrl: string;
  sourceRef: string;
  sourceArchiveUrl: string;
  modifiedNotice: string;
  modifiedDate: string;
  warrantyNotice: string;
  conveyanceNotice: string;
  sourceConfigured: boolean;
}

export const LEGAL_CONFIG: LegalConfig = {
  deploymentName: fromEnv(env.VITE_ARCREEL_LEGAL_DEPLOYMENT_NAME, "CaMeL ArcReel"),
  serviceModel: fromEnv(env.VITE_ARCREEL_LEGAL_SERVICE_MODEL, "free"),
  apiRelayName: fromEnv(env.VITE_ARCREEL_LEGAL_API_RELAY_NAME, "CaMeL"),
  license: "AGPL-3.0",
  upstreamName: "ArcReel",
  upstreamUrl,
  noticeText: `Powered by ArcReel — ${upstreamUrl}`,
  licenseUrl: fromEnv(
    env.VITE_ARCREEL_LEGAL_LICENSE_URL,
    "https://github.com/ArcReel/ArcReel/blob/main/LICENSE",
  ),
  noticeUrl: fromEnv(
    env.VITE_ARCREEL_LEGAL_NOTICE_URL,
    "https://github.com/ArcReel/ArcReel/blob/main/NOTICE",
  ),
  sourceUrl,
  sourceRef: fromEnv(env.VITE_ARCREEL_LEGAL_SOURCE_REF, ""),
  sourceArchiveUrl: fromEnv(env.VITE_ARCREEL_LEGAL_SOURCE_ARCHIVE_URL, ""),
  modifiedNotice: fromEnv(
    env.VITE_ARCREEL_LEGAL_MODIFIED_NOTICE,
    "This deployment runs a modified version of ArcReel.",
  ),
  modifiedDate: fromEnv(env.VITE_ARCREEL_LEGAL_MODIFIED_DATE, "2026-07-09"),
  warrantyNotice: "ArcReel is provided without warranty under AGPL-3.0.",
  conveyanceNotice: "You may receive and convey the covered work under AGPL-3.0.",
  sourceConfigured: sourceUrl.length > 0,
};
