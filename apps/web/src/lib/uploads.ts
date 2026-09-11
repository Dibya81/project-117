/**
 * Document upload pipeline client.
 *
 * Lifecycle surfaced to the UI:
 *   UPLOADING → PROCESSING → OCR → INDEXING → GRAPH_UPDATE → READY | FAILED
 *
 * The backend performs OCR/indexing asynchronously after upload; this module
 * polls the document record until it settles, so the UI shows real state.
 */
import { api, ApiError } from "./api";
import type { DocumentRecord } from "@/types";

export type UploadStage =
  | "uploading"
  | "processing"
  | "ocr"
  | "indexing"
  | "graph_update"
  | "ready"
  | "failed";

export interface UploadProgress {
  file: File;
  stage: UploadStage;
  percent: number; // upload transfer percent (0-100)
  document?: DocumentRecord;
  error?: string;
}

const MAX_BYTES = 100 * 1024 * 1024;
const ACCEPTED = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "image/png",
  "image/jpeg",
  "image/tiff",
];

export function validate(file: File): string | null {
  if (file.size > MAX_BYTES) return "file exceeds 100 MB limit";
  if (file.type && !ACCEPTED.includes(file.type)) return `unsupported type: ${file.type}`;
  return null;
}

function stageFromStatus(status: DocumentRecord["status"]): UploadStage {
  switch (status) {
    case "stored":
      return "processing";
    case "indexing":
      return "indexing";
    case "indexed":
      return "ready";
    case "failed":
      return "failed";
  }
}

export async function uploadDocument(
  file: File,
  onProgress: (p: UploadProgress) => void,
): Promise<DocumentRecord> {
  const invalid = validate(file);
  if (invalid) {
    const err = { file, stage: "failed" as const, percent: 0, error: invalid };
    onProgress(err);
    throw new ApiError(422, "validation", invalid);
  }

  const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
  const form = new FormData();
  form.append("files", file);

  onProgress({ file, stage: "uploading", percent: 0 });

  // XHR (not fetch) for real upload progress events.
  const uploaded = await new Promise<{ documents: DocumentRecord[] }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${base}/api/documents/upload`);
    const roles = window.sessionStorage.getItem("p117.roles");
    if (roles) xhr.setRequestHeader("X-P117-Roles", roles);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress({
          file,
          stage: "uploading",
          percent: Math.round((e.loaded / e.total) * 100),
        });
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new ApiError(xhr.status, "parse", "invalid upload response"));
        }
      } else {
        reject(new ApiError(xhr.status, "upload_failed", xhr.statusText));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "offline", "backend unreachable"));
    xhr.send(form);
  });

  const document = uploaded.documents[0];
  onProgress({ file, stage: "processing", percent: 100, document });

  // Poll until the ingestion pipeline settles (indexed | failed).
  const deadline = Date.now() + 5 * 60 * 1000;
  let current = document;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 2000));
    current = await api.documents.get(document.id);
    const stage = stageFromStatus(current.status);
    onProgress({ file, stage, percent: 100, document: current });
    if (stage === "ready" || stage === "failed") break;
  }
  if (current.status === "failed") {
    throw new ApiError(422, "indexing_failed", `indexing failed for ${file.name}`);
  }
  return current;
}
