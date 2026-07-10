import { create } from "zustand";
import { API } from "@/api";
import type { Asset, AssetLibrary, AssetType } from "@/types/asset";

interface AssetsStore {
  byType: Record<AssetType, Asset[]>;
  library: AssetLibrary;
  loadList: (library: AssetLibrary, type: AssetType, q?: string) => Promise<void>;
  addAsset: (asset: Asset) => void;
  updateAsset: (asset: Asset) => void;
  syncAsset: (id: string, type: AssetType) => Promise<void>;
  deleteAsset: (id: string, type: AssetType) => Promise<void>;
}

export const useAssetsStore = create<AssetsStore>((set) => ({
  byType: { character: [], scene: [], prop: [] },
  library: "tenant",
  loadList: async (library, type, q) => {
    const res = await API.listAssets({ library, type, q });
    set((s) => ({ library, byType: { ...s.byType, [type]: res.items } }));
  },
  addAsset: (asset) =>
    set((s) => ({
      byType: { ...s.byType, [asset.type]: [asset, ...s.byType[asset.type]] },
    })),
  updateAsset: (asset) =>
    set((s) => ({
      byType: {
        ...s.byType,
        [asset.type]: s.byType[asset.type].map((a) => (a.id === asset.id ? asset : a)),
      },
    })),
  syncAsset: async (id, type) => {
    const { asset } = await API.syncAsset(id, true);
    set((s) => ({
      byType: { ...s.byType, [type]: s.byType[type].map((a) => (a.id === id ? asset : a)) },
    }));
  },
  deleteAsset: async (id, type) => {
    await API.deleteAsset(id);
    set((s) => ({
      byType: { ...s.byType, [type]: s.byType[type].filter((a) => a.id !== id) },
    }));
  },
}));
