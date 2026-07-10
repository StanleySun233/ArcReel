import { afterEach, describe, expect, it, vi } from "vitest";

const legalEnvKeys = [
  "VITE_ARCREEL_LEGAL_DEPLOYMENT_NAME",
  "VITE_ARCREEL_LEGAL_SERVICE_MODEL",
  "VITE_ARCREEL_LEGAL_API_RELAY_NAME",
  "VITE_ARCREEL_LEGAL_UPSTREAM_URL",
  "VITE_ARCREEL_LEGAL_LICENSE_URL",
  "VITE_ARCREEL_LEGAL_NOTICE_URL",
  "VITE_ARCREEL_LEGAL_SOURCE_URL",
  "VITE_ARCREEL_LEGAL_SOURCE_REF",
  "VITE_ARCREEL_LEGAL_SOURCE_ARCHIVE_URL",
  "VITE_ARCREEL_LEGAL_MODIFIED_NOTICE",
  "VITE_ARCREEL_LEGAL_MODIFIED_DATE",
] as const;

async function loadLegalConfig(overrides: Record<string, string | undefined> = {}) {
  vi.resetModules();
  vi.unstubAllEnvs();

  for (const key of legalEnvKeys) {
    vi.stubEnv(key, "");
  }
  for (const [key, value] of Object.entries(overrides)) {
    vi.stubEnv(key, value);
  }

  return import("./legal");
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("LEGAL_CONFIG", () => {
  it("provides default AGPL compliance data", async () => {
    const { LEGAL_CONFIG } = await loadLegalConfig();

    expect(LEGAL_CONFIG.upstreamName).toBe("ArcReel");
    expect(LEGAL_CONFIG.upstreamUrl).toBe("https://github.com/ArcReel/ArcReel");
    expect(LEGAL_CONFIG.license).toBe("AGPL-3.0");
    expect(LEGAL_CONFIG.licenseUrl).toBe("https://github.com/ArcReel/ArcReel/blob/main/LICENSE");
    expect(LEGAL_CONFIG.noticeUrl).toBe("https://github.com/ArcReel/ArcReel/blob/main/NOTICE");
    expect(LEGAL_CONFIG.noticeText).toContain("https://github.com/ArcReel/ArcReel");
    expect(LEGAL_CONFIG.modifiedNotice).toContain("modified version of ArcReel");
    expect(LEGAL_CONFIG.modifiedDate).toBe("2026-07-09");
    expect(LEGAL_CONFIG.deploymentName).toBe("CaMeL ArcReel");
    expect(LEGAL_CONFIG.serviceModel).toBe("free");
    expect(LEGAL_CONFIG.apiRelayName).toBe("CaMeL");
    expect(LEGAL_CONFIG.sourceUrl).toBe("");
    expect(LEGAL_CONFIG.sourceConfigured).toBe(false);
  });

  it("marks source as configured when a deployed source URL is present", async () => {
    const { LEGAL_CONFIG } = await loadLegalConfig({
      VITE_ARCREEL_LEGAL_SOURCE_URL: "https://git.example.com/camel/arcreel",
      VITE_ARCREEL_LEGAL_SOURCE_REF: "refs/heads/main",
      VITE_ARCREEL_LEGAL_SOURCE_ARCHIVE_URL: "https://git.example.com/camel/arcreel/archive/main.tar.gz",
    });

    expect(LEGAL_CONFIG.sourceUrl).toBe("https://git.example.com/camel/arcreel");
    expect(LEGAL_CONFIG.sourceRef).toBe("refs/heads/main");
    expect(LEGAL_CONFIG.sourceArchiveUrl).toBe(
      "https://git.example.com/camel/arcreel/archive/main.tar.gz",
    );
    expect(LEGAL_CONFIG.sourceConfigured).toBe(true);
  });
});
