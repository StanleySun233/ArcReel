import { waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/stores/auth-store";

describe("useAuthStore", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.localStorage.clear();
    useAuthStore.setState(useAuthStore.getInitialState(), true);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads camel auth mode and providers from /api/v1/auth/status", async () => {
    const providers = [
      {
        id: "camel",
        label: "CaMeL",
        login_url: "/api/v1/auth/camel/login",
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        enabled: true,
        mode: "camel",
        providers,
      }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    useAuthStore.getState().initialize();

    await waitFor(() => {
      expect(useAuthStore.getState()).toMatchObject({
        authMode: "camel",
        providers,
        authStatus: {
          enabled: true,
          mode: "camel",
          providers,
        },
        isLoading: false,
      });
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/status",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });
});
