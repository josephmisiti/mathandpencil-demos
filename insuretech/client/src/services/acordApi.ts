import { useMemo } from "react";

const rawBaseUrl = (import.meta.env.VITE_ACORD_API_BASE_URL || "").trim();
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");
const API_TOKEN = (import.meta.env.VITE_ACORD_API_TOKEN || "").trim();

export interface UploadResponse {
  job_id: string;
  status?: string;
  message?: string;
}

export interface ProgressResponse {
  status: "queued" | "uploading" | "processing" | "completed" | "failed" | string;
  stage?: string;
  progress?: number;
  message?: string;
  result?: Record<string, unknown> | null;
  error?: string;
}

const missingBaseUrlError = new Error(
  "ACORD API base URL is not configured. Set VITE_ACORD_API_BASE_URL in your environment."
);

function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (API_TOKEN) {
    headers["Authorization"] = `Bearer ${API_TOKEN}`;
  }
  return headers;
}

export function uploadPdf(
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadResponse> {
  if (!API_BASE_URL) {
    return Promise.reject(missingBaseUrlError);
  }

  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/upload`);
    xhr.responseType = "json";

    const headers = buildHeaders();
    Object.entries(headers).forEach(([key, value]) => {
      xhr.setRequestHeader(key, value);
    });

    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable) return;
      const percent = Math.round((event.loaded / event.total) * 100);
      onProgress(percent);
    };

    xhr.onerror = () => {
      reject(new Error("Network error while uploading PDF."));
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response: UploadResponse =
            xhr.response && typeof xhr.response === "object"
              ? (xhr.response as UploadResponse)
              : JSON.parse(xhr.responseText || "{}");

          if (!response || !response.job_id) {
            reject(new Error("Upload succeeded but job ID was not returned."));
            return;
          }
          resolve(response);
        } catch (error) {
          reject(new Error(`Unexpected upload response: ${String(error)}`));
        }
      } else {
        let message = xhr.responseText || `Upload failed with status ${xhr.status}`;
        if (xhr.response && typeof xhr.response === "object") {
          const maybeMessage = (xhr.response as { message?: string }).message;
          if (maybeMessage) {
            message = maybeMessage;
          }
        }
        reject(new Error(message));
      }
    };

    xhr.send(formData);
  });
}

export async function fetchProgress(
  jobId: string,
  signal?: AbortSignal
): Promise<ProgressResponse> {
  if (!API_BASE_URL) {
    throw missingBaseUrlError;
  }

  const response = await fetch(`${API_BASE_URL}/progress/${encodeURIComponent(jobId)}`, {
    method: "GET",
    headers: buildHeaders(),
    signal
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Progress request failed with status ${response.status}`);
  }

  const data = (await response.json()) as ProgressResponse;
  return data;
}

export function useAcordApiConfig(): {
  baseUrl: string;
  hasToken: boolean;
} {
  return useMemo(
    () => ({
      baseUrl: API_BASE_URL,
      hasToken: Boolean(API_TOKEN)
    }),
    []
  );
}
