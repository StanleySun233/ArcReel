import { memo, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Edit2, RefreshCcw, Trash2, User as UserIcon, Landmark, Package } from "lucide-react";
import { API } from "@/api";
import { formatDate } from "@/utils/date-format";
import type { Asset } from "@/types/asset";
import { AssetThumb } from "./AssetThumb";

interface Props {
  asset: Asset;
  onEdit: (asset: Asset) => void;
  onDelete: (asset: Asset) => void;
  onSync?: (asset: Asset) => void;
}

const TYPE_ICON = { character: UserIcon, scene: Landmark, prop: Package };

const SHORT_DATE_OPTS: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };

export const AssetCard = memo(AssetCardImpl);

function AssetCardImpl({ asset, onEdit, onDelete, onSync }: Props) {
  const { t, i18n } = useTranslation("assets");
  const Icon = TYPE_ICON[asset.type];
  const [signedImage, setSignedImage] = useState<{ fileId: string; url: string } | null>(null);
  const imageUrl = signedImage?.fileId === asset.image_file_id
    ? signedImage.url
    : API.getGlobalAssetUrl(asset.image_path, asset.updated_at);
  const formattedDate = asset.updated_at
    ? formatDate(asset.updated_at, i18n.language, SHORT_DATE_OPTS, "")
    : "";

  useEffect(() => {
    let canceled = false;
    if (!asset.image_file_id) return;
    void API.getFileSignedUrl(asset.image_file_id)
      .then((res) => {
        if (!canceled) setSignedImage({ fileId: asset.image_file_id!, url: res.url });
      })
      .catch(() => {
        if (!canceled) setSignedImage(null);
      });
    return () => {
      canceled = true;
    };
  }, [asset.image_file_id, asset.updated_at]);

  return (
    <div className="group relative overflow-hidden rounded-[10px] border border-hairline-soft bg-bg-grad-a/55 transition-[transform,border-color] motion-safe:hover:-translate-y-0.5 hover:border-hairline">
      <div className="relative">
        <AssetThumb
          imageUrl={imageUrl}
          alt={asset.name}
          fallback={<Icon className="h-10 w-10 text-text-4" />}
          variant="display"
        />
        <span className="pointer-events-none absolute right-2 top-2 rounded border border-hairline bg-bg-grad-b/70 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-text-3 backdrop-blur-sm">
          {t(`type.${asset.type}`)}
        </span>
      </div>
      <div className="p-3">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13.5px] font-semibold text-text">{asset.name}</div>
            {asset.description && (
              <div className="mt-1 line-clamp-2 text-[12px] leading-[1.55] text-text-3">
                {asset.description}
              </div>
            )}
            {formattedDate ? (
              <div className="mt-2 flex items-center gap-2 font-mono text-[10.5px] text-text-4">
                <span className="tabular-nums">{t("meta_updated_at", { date: formattedDate })}</span>
              </div>
            ) : null}
            <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-text-4">
              {t(`library.${asset.library}`)}
            </div>
          </div>
          <div className="flex flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            {asset.can_sync && onSync ? (
              <button
                type="button"
                onClick={() => onSync(asset)}
                aria-label={t("sync")}
                className="rounded-[5px] p-1 text-text-4 transition-colors hover:text-accent-2 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => onEdit(asset)}
              disabled={!asset.can_write}
              aria-label={t("edit")}
              className="rounded-[5px] p-1 text-text-4 transition-colors hover:text-text disabled:cursor-not-allowed disabled:opacity-35 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <Edit2 className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onDelete(asset)}
              disabled={!asset.can_write}
              aria-label={t("delete")}
              className="rounded-[5px] p-1 text-text-4 transition-colors hover:text-warm-bright disabled:cursor-not-allowed disabled:opacity-35 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warm-ring"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
