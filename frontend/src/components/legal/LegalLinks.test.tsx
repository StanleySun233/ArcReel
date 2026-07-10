import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LegalLinks } from "./LegalLinks";
import type { LegalConfig } from "@/config/legal";

const baseConfig: LegalConfig = {
  upstreamName: "ArcReel",
  upstreamUrl: "https://github.com/ArcReel/ArcReel",
};

function renderLegalLinks(overrides: Partial<LegalConfig> = {}) {
  render(<LegalLinks config={{ ...baseConfig, ...overrides }} />);
}

describe("LegalLinks", () => {
  it("renders only upstream attribution", () => {
    renderLegalLinks();

    expect(screen.getByText(/Powered by ArcReel/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: baseConfig.upstreamUrl })).toHaveAttribute(
      "href",
      baseConfig.upstreamUrl,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/AGPL|NOTICE|License|Deployed source|Source archive/i)).not.toBeInTheDocument();
  });
});
