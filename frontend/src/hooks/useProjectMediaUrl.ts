import { useEffect, useState } from "react";
import { API } from "@/api";
import { getAuthHeader } from "@/utils/auth";

function isFileId(value: string | null | undefined): value is string {
  return typeof value === "string" && value.startsWith("fil_");
}

function isDirectUrl(value: string): boolean {
  return /^(https?:|blob:|data:)/.test(value);
}

function extractProjectPath(projectName: string, value: string): string {
  const prefix = `/api/v1/files/${encodeURIComponent(projectName)}/`;
  return value.startsWith(prefix) ? value.slice(prefix.length) : value;
}

export function useProjectMediaUrl(
  projectName: string,
  assetPath: string | null | undefined,
  fingerprint?: number | string | null,
): string | null {
  const [resolved, setResolved] = useState<{ key: string; url: string } | null>(null);
  const directUrl = assetPath && isDirectUrl(assetPath) ? assetPath : null;
  const authHeader = getAuthHeader();
  const fallbackUrl =
    assetPath && !directUrl && !isFileId(assetPath) && !authHeader
      ? API.getFileUrl(projectName, extractProjectPath(projectName, assetPath), fingerprint)
      : null;
  const key = assetPath ? `${projectName}:${assetPath}:${fingerprint ?? ""}` : "";

  useEffect(() => {
    let cancelled = false;
    if (!assetPath || directUrl || fallbackUrl) {
      return;
    }

    if (isFileId(assetPath)) {
      void API.getFileSignedUrl(assetPath)
        .then((res) => {
          if (!cancelled) setResolved({ key, url: res.url });
        })
        .catch(() => {
          if (!cancelled) setResolved(null);
        });
      return () => {
        cancelled = true;
      };
    }

    if (!authHeader) {
      return;
    }

    const url = API.getFileUrl(projectName, extractProjectPath(projectName, assetPath), fingerprint);
    void fetch(url, { headers: { Authorization: authHeader } })
      .then((response) => {
        if (!response.ok) throw new Error(response.statusText);
        return response.blob();
      })
      .then((blob) => {
        const objectUrl = URL.createObjectURL(blob);
        if (cancelled) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setResolved((prev) => {
          if (prev?.url.startsWith("blob:")) URL.revokeObjectURL(prev.url);
          return { key, url: objectUrl };
        });
      })
      .catch(() => {
        if (!cancelled) setResolved(null);
      });

    return () => {
      cancelled = true;
    };
  }, [assetPath, authHeader, directUrl, fallbackUrl, fingerprint, key, projectName]);

  useEffect(() => () => {
    if (resolved?.url.startsWith("blob:")) URL.revokeObjectURL(resolved.url);
  }, [resolved]);

  return directUrl ?? fallbackUrl ?? (resolved?.key === key ? resolved.url : null);
}
