import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  API,
  type CamelBootstrapResult,
  type CamelBootstrapStatus,
} from "@/api";
import { useAuthStore } from "@/stores/auth-store";
import { useConfigStatusStore } from "@/stores/config-status-store";
import { CamelProviderBootstrapModal } from "./CamelProviderBootstrapModal";

function completedStatus(): CamelBootstrapStatus {
  return { needed: false, completed: true };
}

function neededStatus(): CamelBootstrapStatus {
  return {
    needed: true,
    completed: false,
    camel_user_id: "user-1",
    providers: [
      {
        media: "image",
        provider_name: "CaMeL Image",
        base_url: "https://camel.example",
        endpoint: "/v1/images",
        models: ["imagen-4"],
        token_name: "camel-arcreel-user-1-image",
      },
      {
        media: "text",
        provider_name: "CaMeL Text",
        base_url: "https://camel.example",
        endpoint: "/v1/chat/completions",
        models: ["gpt-5"],
        token_name: "camel-arcreel-user-1-text",
      },
      {
        media: "video",
        provider_name: "CaMeL Video",
        base_url: "https://camel.example",
        endpoint: "/v1/videos",
        models: ["veo-3"],
        token_name: "camel-arcreel-user-1-video",
      },
      {
        media: "audio",
        provider_name: "CaMeL Audio",
        base_url: "https://camel.example",
        endpoint: "/v1/audio/speech",
        models: ["tts-1"],
        token_name: "camel-arcreel-user-1-audio",
      },
    ],
  };
}

function setBootstrapResult(result: CamelBootstrapResult): void {
  window.history.pushState(
    null,
    "",
    `/app/projects/demo?camel_bootstrap=1&camel_bootstrap_result=${encodeURIComponent(JSON.stringify(result))}`,
  );
}

describe("CamelProviderBootstrapModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useConfigStatusStore.setState(useConfigStatusStore.getInitialState(), true);
    useAuthStore.setState({
      token: "tok",
      username: "alice",
      isAuthenticated: true,
      isLoading: false,
      authStatus: { enabled: true, mode: "camel", providers: [] },
      authMode: "camel",
      providers: [],
    });
    window.history.pushState(null, "", "/app/projects/demo");
    vi.spyOn(API, "getCamelBootstrapStatus").mockResolvedValue(completedStatus());
    vi.spyOn(API, "startCamelBootstrap").mockReturnValue(new Promise<never>(() => {}));
  });

  it("shows the provider plan when bootstrap is needed and starts setup from the current path", async () => {
    vi.spyOn(API, "getCamelBootstrapStatus").mockResolvedValue(neededStatus());

    window.history.pushState(null, "", "/app/projects/demo?view=settings#providers");
    render(<CamelProviderBootstrapModal />);

    expect(await screen.findByText("CaMeL Image")).toBeInTheDocument();
    expect(screen.getByText("CaMeL Audio")).toBeInTheDocument();
    expect(screen.getByText("camel-arcreel-user-1-image")).toBeInTheDocument();
    expect(screen.getByText("/v1/videos - veo-3")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start setup" }));

    await waitFor(() => {
      expect(API.startCamelBootstrap).toHaveBeenCalledWith(
        "create",
        "/app/projects/demo?view=settings#providers",
      );
    });
  });

  it("shows conflicting token links and retry setup", async () => {
    setBootstrapResult({
      completed: false,
      error: "camel_token_conflict",
      conflicts: [
        {
          media: "image",
          token_name: "camel-arcreel-user-1-image",
          delete_url: "https://camel.example/tokens/image/delete",
        },
      ],
    });

    render(<CamelProviderBootstrapModal />);

    expect(await screen.findByText("CaMeL already has tokens with these names. Delete them in CaMeL, then retry.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry setup" })).toBeInTheDocument();
    expect(screen.getByText("camel-arcreel-user-1-image")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /camel-arcreel-user-1-image/ })).toHaveAttribute(
      "href",
      "https://camel.example/tokens/image/delete",
    );
  });

  it("shows deletion links after partial bootstrap failure", async () => {
    setBootstrapResult({
      completed: false,
      error: "partial_bootstrap_failed",
      created_tokens: [
        {
          media: "video",
          token_name: "camel-arcreel-user-1-video",
          delete_url: "https://camel.example/tokens/video/delete",
        },
        {
          media: "audio",
          token_name: "camel-arcreel-user-1-audio",
          delete_url: "https://camel.example/tokens/audio/delete",
        },
      ],
    });

    render(<CamelProviderBootstrapModal />);

    expect(await screen.findByText("CaMeL tokens were created, but ArcReel provider setup did not complete. Delete these tokens, then retry.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /camel-arcreel-user-1-video/ })).toHaveAttribute(
      "href",
      "https://camel.example/tokens/video/delete",
    );
    expect(screen.getByRole("link", { name: /camel-arcreel-user-1-audio/ })).toHaveAttribute(
      "href",
      "https://camel.example/tokens/audio/delete",
    );
  });

  it("refreshes config status after success and can be closed", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    useConfigStatusStore.setState({ refresh });
    setBootstrapResult({
      completed: true,
      providers: [
        {
          media: "image",
          provider_id: 1,
          provider_name: "CaMeL Image",
          models: ["imagen-4"],
        },
      ],
    });

    render(<CamelProviderBootstrapModal />);

    expect(await screen.findByText("Bootstrap completed. Provider configuration is refreshing.")).toBeInTheDocument();
    await waitFor(() => {
      expect(refresh).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Done" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
