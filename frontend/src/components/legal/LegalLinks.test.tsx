import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LegalLinks } from "./LegalLinks";
import type { LegalConfig } from "@/config/legal";

const baseConfig: LegalConfig = {
  deploymentName: "CaMeL ArcReel",
  serviceModel: "free",
  apiRelayName: "CaMeL",
  license: "AGPL-3.0",
  upstreamName: "ArcReel",
  upstreamUrl: "https://github.com/ArcReel/ArcReel",
  noticeText: "Powered by ArcReel — https://github.com/ArcReel/ArcReel",
  licenseUrl: "https://github.com/ArcReel/ArcReel/blob/main/LICENSE",
  noticeUrl: "https://github.com/ArcReel/ArcReel/blob/main/NOTICE",
  sourceUrl: "",
  sourceRef: "",
  sourceArchiveUrl: "",
  modifiedNotice: "This deployment runs a modified version of ArcReel.",
  modifiedDate: "2026-07-09",
  warrantyNotice: "ArcReel is provided without warranty under AGPL-3.0.",
  conveyanceNotice: "You may receive and convey the covered work under AGPL-3.0.",
  sourceConfigured: false,
};

function renderLegalLinks(overrides: Partial<LegalConfig> = {}) {
  render(<LegalLinks config={{ ...baseConfig, ...overrides }} />);
}

describe("LegalLinks", () => {
  it("renders upstream attribution and AGPL compliance text", () => {
    renderLegalLinks();

    expect(screen.getByText(/Powered by ArcReel/)).toBeInTheDocument();
    expect(screen.getByText(/Upstream repository:/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "AGPL-3.0" })).toHaveAttribute(
      "href",
      baseConfig.licenseUrl,
    );
    expect(screen.getByRole("link", { name: baseConfig.noticeUrl })).toHaveAttribute(
      "href",
      baseConfig.noticeUrl,
    );
    expect(
      screen.getByText(/This deployment runs a modified version of ArcReel\. Modified date: 2026-07-09\./),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/CaMeL ArcReel is offered free of charge with CaMeL as the API relay/),
    ).toBeInTheDocument();
    expect(screen.getByText(baseConfig.warrantyNotice)).toBeInTheDocument();
    expect(screen.getByText(baseConfig.conveyanceNotice)).toBeInTheDocument();
  });

  it("shows a compliance warning when deployed source is not configured", () => {
    renderLegalLinks();

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Legal compliance warning");
    expect(alert).toHaveTextContent("VITE_ARCREEL_LEGAL_SOURCE_URL");
  });

  it("renders deployed source and source archive when configured", () => {
    const sourceUrl = "https://git.example.com/camel/arcreel";
    const sourceArchiveUrl = "https://git.example.com/camel/arcreel/archive/main.tar.gz";

    renderLegalLinks({
      sourceUrl,
      sourceRef: "refs/heads/main",
      sourceArchiveUrl,
      sourceConfigured: true,
    });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText(/Deployed source:/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: `${sourceUrl} (refs/heads/main)` })).toHaveAttribute(
      "href",
      sourceUrl,
    );
    expect(screen.getByText(/Source archive:/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: sourceArchiveUrl })).toHaveAttribute(
      "href",
      sourceArchiveUrl,
    );
  });
});
