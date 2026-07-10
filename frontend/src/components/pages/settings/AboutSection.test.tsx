import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { API } from "@/api";
import { AboutSection } from "./AboutSection";
import type { GetSystemVersionResponse } from "@/types";

vi.mock("@/components/legal/LegalLinks", () => ({
  LegalLinks: () => <div data-testid="legal-links" />,
}));

function makeVersionResponse(): GetSystemVersionResponse {
  return {
    current: { version: "0.20.1" },
    latest: null,
    has_update: false,
    checked_at: "2026-07-09T00:00:00Z",
    update_check_error: null,
  };
}

describe("AboutSection", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders LegalLinks in the legal section", async () => {
    vi.spyOn(API, "getSystemVersion").mockResolvedValue(makeVersionResponse());

    render(<AboutSection />);

    expect(await screen.findByTestId("legal-links")).toBeInTheDocument();
  });
});
