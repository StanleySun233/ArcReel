import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAssetsStore } from "./assets-store";
import { API } from "@/api";
import type { Asset } from "@/types/asset";

const asset = (patch: Partial<Asset> = {}): Asset => ({
  id: "1",
  binding_id: "1",
  asset_id: "ast_1",
  type: "scene",
  name: "A",
  description: "",
  voice_style: "",
  image_file_id: null,
  image_path: null,
  source_project: null,
  library: "tenant",
  parent_binding_id: null,
  can_write: true,
  can_sync: false,
  updated_at: null,
  ...patch,
});

describe("useAssetsStore", () => {
  beforeEach(() => {
    useAssetsStore.setState({ byType: { character: [], scene: [], prop: [] }, library: "tenant" });
    vi.restoreAllMocks();
  });

  it("loads list by type", async () => {
    vi.spyOn(API, "listAssets" as any).mockResolvedValue({ items: [asset()] });
    await useAssetsStore.getState().loadList("personal", "scene");
    expect(useAssetsStore.getState().byType.scene).toHaveLength(1);
    expect(useAssetsStore.getState().library).toBe("personal");
  });

  it("removes asset locally after delete", async () => {
    useAssetsStore.setState({ byType: { character: [], scene: [asset()], prop: [] }, library: "tenant" });
    vi.spyOn(API, "deleteAsset" as any).mockResolvedValue(undefined);
    await useAssetsStore.getState().deleteAsset("1", "scene");
    expect(useAssetsStore.getState().byType.scene).toHaveLength(0);
  });

  it("replaces snapshot locally after sync", async () => {
    useAssetsStore.setState({
      byType: { character: [], scene: [asset({ description: "old", can_sync: true })], prop: [] },
      library: "tenant",
    });
    vi.spyOn(API, "syncAsset" as any).mockResolvedValue({ asset: asset({ description: "new", can_sync: true }) });
    await useAssetsStore.getState().syncAsset("1", "scene");
    expect(useAssetsStore.getState().byType.scene[0].description).toBe("new");
  });
});
