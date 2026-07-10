export type AssetType = "character" | "scene" | "prop";
export type AssetLibrary = "tenant" | "personal";

export interface Asset {
  id: string;
  binding_id: string;
  asset_id: string;
  type: AssetType;
  name: string;
  description: string;
  voice_style: string;
  image_file_id: string | null;
  image_path: string | null;
  source_project: string | null;
  library: AssetLibrary;
  parent_binding_id: string | null;
  can_write: boolean;
  can_sync: boolean;
  updated_at: string | null;
}

export interface AssetCreatePayload {
  library: AssetLibrary;
  type: AssetType;
  name: string;
  description?: string;
  voice_style?: string;
  image_file_id?: string | null;
}

export interface AssetUpdatePayload {
  name?: string;
  description?: string;
  voice_style?: string;
  image_file_id?: string | null;
}
