import { describe, expect, it } from "vitest";

import { LEGAL_CONFIG } from "./legal";

describe("LEGAL_CONFIG", () => {
  it("provides upstream attribution data", () => {
    expect(LEGAL_CONFIG.upstreamName).toBe("ArcReel");
    expect(LEGAL_CONFIG.upstreamUrl).toBe("https://github.com/ArcReel/ArcReel");
  });
});
