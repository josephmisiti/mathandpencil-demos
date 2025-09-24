import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileError, FileRejection, useDropzone } from "react-dropzone";
import {
  ProgressResponse,
  fetchProgress,
  geocodeAddress,
  useAcordApiConfig
} from "../services/acordApi";

interface UploadResponse {
  job_id: string;
  status?: string;
  message?: string;
}

type UploadPhase = "idle" | "uploading" | "processing" | "completed" | "error";

interface UploadState {
  phase: UploadPhase;
  uploadProgress: number;
  processingProgress: number;
  message: string;
  error: string | null;
  jobId: string | null;
  fileName: string | null;
  result: ProgressResponse["result"];
}

const initialState: UploadState = {
  phase: "idle",
  uploadProgress: 0,
  processingProgress: 0,
  message: "",
  error: null,
  jobId: null,
  fileName: null,
  result: null
};

interface PdfUploadDropzoneProps {
  className?: string;
  onComplete?: (payload: ProgressResponse["result"]) => void;
}

export default function PdfUploadDropzone({
  className,
  onComplete
}: PdfUploadDropzoneProps) {
  const [state, setState] = useState<UploadState>(initialState);
  const [hasTouched, setHasTouched] = useState(false);
  const pollIntervalRef = useRef<number | null>(null);
  const { baseUrl: apiBaseUrl, hasToken } = useAcordApiConfig();

  const apiConfigured = useMemo(() => Boolean(apiBaseUrl), [apiBaseUrl]);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current !== null) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Build headers just like endpoint_test.py
  const buildHeaders = useCallback(() => {
    const headers: Record<string, string> = {};
    if (hasToken) {
      const token = (import.meta.env.VITE_ACORD_API_TOKEN || "").trim();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }
    return headers;
  }, [hasToken]);

  // Upload PDF - matches endpoint_test.py lines 47-69
  const uploadPdf = useCallback(
    async (file: File): Promise<UploadResponse> => {
      if (!apiBaseUrl) {
        throw new Error("API base URL not configured");
      }

      const formData = new FormData();
      formData.append("file", file);

      const headers = buildHeaders();

      const response = await fetch(`${apiBaseUrl}/upload`, {
        method: "POST",
        headers,
        body: formData
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Upload failed: ${response.status}`);
      }

      const data = (await response.json()) as UploadResponse;

      if (!data.job_id) {
        throw new Error("No job ID returned from upload");
      }

      return data;
    },
    [apiBaseUrl, buildHeaders]
  );

  // Use the existing fetchProgress function from acordApi.ts

  // Poll progress continuously - matches endpoint_test.py lines 71-157
  const startPolling = useCallback(
    (jobId: string) => {
      const MAX_WAIT_TIME = 300000; // 5 minutes in ms
      const POLL_INTERVAL = 2500; // 2.5 seconds in ms
      const startTime = Date.now();

      const poll = async () => {
        const elapsed = Date.now() - startTime;
        if (elapsed > MAX_WAIT_TIME) {
          setState((prev) => ({
            ...prev,
            phase: "error",
            error: "Timeout after 5 minutes"
          }));
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          return;
        }

        try {
          console.log(`[DEBUG] Calling fetchProgress for job: ${jobId}`);
          const progressData = await fetchProgress(jobId);
          console.log(`[DEBUG] fetchProgress response:`, progressData);

          // Extract data just like endpoint_test.py lines 92-96
          const status = progressData.status;
          const stage = progressData.stage || "";
          const progressPct = progressData.progress || 0;
          const message = progressData.message || "";

          // Normalize progress to 0-100 range
          let normalizedProgress = 0;
          if (typeof progressPct === "number") {
            if (progressPct <= 1 && progressPct >= 0) {
              normalizedProgress = Math.round(progressPct * 100);
            } else {
              normalizedProgress = Math.round(
                Math.max(0, Math.min(100, progressPct))
              );
            }
          }

          console.log(
            `[DEBUG] Updating progress: ${normalizedProgress}%, status: ${status}, stage: ${stage}, message: ${message}`
          );
          setState((prev) => ({
            ...prev,
            processingProgress: normalizedProgress,
            message: message || stage || prev.message
          }));

          // Handle completion like endpoint_test.py lines 102-143
          if (status === "completed") {
            console.log("🎉 Processing completed successfully!");
            console.log("📊 Final results:", progressData.result);

            // Log structured data like endpoint_test.py does
            if (progressData.result) {
              const result = progressData.result;
              console.log(`📄 ACORD Type: ${result.acord_type || "Unknown"}`);
              console.log(
                `📊 OCR Text Length: ${result.text_length || 0} characters`
              );

              if (result.extracted_data) {
                console.log("🎯 Structured data extracted successfully");
                console.log("📋 Extracted Data:", result.extracted_data);

                // Send extracted data to geocoding API
                console.log("🌍 Sending ACORD data to geocoding API...");
                geocodeAddress(result.extracted_data as Record<string, unknown>)
                  .then((geocodeResult) => {
                    console.info("🗺️ Geocoding completed successfully!");
                    console.info(
                      "📍 Extracted Address:",
                      geocodeResult.address
                    );

                    if (
                      geocodeResult.geocoding_results?.results &&
                      geocodeResult.geocoding_results.results.length > 0
                    ) {
                      const firstResult =
                        geocodeResult.geocoding_results.results[0];
                      console.info("🌍 Google Geocoding Results:");
                      console.info(
                        "   📍 Formatted Address:",
                        firstResult.formatted_address
                      );
                      console.info("   🗺️ Coordinates:", {
                        lat: firstResult.geometry.location.lat,
                        lng: firstResult.geometry.location.lng
                      });

                      // Update URL with geocoding results
                      const url = new URL(window.location.href);
                      url.searchParams.set(
                        "lat",
                        firstResult.geometry.location.lat.toString()
                      );
                      url.searchParams.set(
                        "lng",
                        firstResult.geometry.location.lng.toString()
                      );
                      url.searchParams.set("zoom", "18");
                      url.searchParams.set(
                        "address",
                        encodeURIComponent(firstResult.formatted_address)
                      );

                      console.info("🔗 Updating URL:", url.toString());
                      window.history.pushState({}, "", url.toString());

                      // Trigger a page reload to update the map
                      window.location.reload();
                    }

                    if (geocodeResult.geocoding_results?.error) {
                      console.warn(
                        "⚠️ Geocoding API error:",
                        geocodeResult.geocoding_results.error
                      );
                    }

                    console.info("📋 Full Geocoding Response:", geocodeResult);
                  })
                  .catch((error) => {
                    console.error("❌ Geocoding failed:", error);
                  });
              }
            }

            setState((prev) => ({
              ...prev,
              phase: "completed",
              processingProgress: 100,
              result: progressData.result || null,
              error: null
            }));

            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }

            onComplete?.(progressData.result || null);
            return;
          }

          // Handle failure like endpoint_test.py lines 145-149
          if (status === "failed") {
            setState((prev) => ({
              ...prev,
              phase: "error",
              error: progressData.error || "Processing failed"
            }));

            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            return;
          }
        } catch (error) {
          setState((prev) => ({
            ...prev,
            phase: "error",
            error:
              error instanceof Error ? error.message : "Progress check failed"
          }));

          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      };

      // Start polling immediately, then every POLL_INTERVAL ms
      console.log(`[DEBUG] Starting polling for job: ${jobId}`);
      poll();
      pollIntervalRef.current = window.setInterval(poll, POLL_INTERVAL);
    },
    [onComplete]
  );

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const beginUpload = useCallback(
    async (file: File) => {
      stopPolling();
      setHasTouched(true);

      setState({
        phase: "uploading",
        uploadProgress: 0,
        processingProgress: 0,
        message: "Uploading PDF...",
        error: null,
        jobId: null,
        fileName: file.name,
        result: null
      });

      try {
        // Simulate upload progress since we're using fetch
        setState((prev) => ({ ...prev, uploadProgress: 100 }));

        const uploadResult = await uploadPdf(file);

        console.info("Upload result:", uploadResult);

        setState((prev) => ({
          ...prev,
          phase: "processing",
          uploadProgress: 100,
          jobId: uploadResult.job_id,
          message: uploadResult.message || "Upload complete. Processing..."
        }));

        // Start polling for progress like endpoint_test.py
        startPolling(uploadResult.job_id);
      } catch (error) {
        stopPolling();
        setState((prev) => ({
          ...prev,
          phase: "error",
          uploadProgress: 0,
          error: error instanceof Error ? error.message : "Upload failed",
          message: "Upload failed."
        }));
      }
    },
    [uploadPdf, startPolling, stopPolling]
  );

  const handleDrop = useCallback(
    (acceptedFiles: File[], rejections: FileRejection[]) => {
      if (!apiConfigured) {
        setState({
          ...initialState,
          phase: "error",
          error:
            "Upload API is not configured. Set VITE_ACORD_API_BASE_URL in your environment."
        });
        return;
      }

      if (rejections.length > 0) {
        const messages = rejections
          .flatMap((item) =>
            item.errors.map((error: FileError) => error.message)
          )
          .join("; ");
        setState({
          ...initialState,
          phase: "error",
          error: messages || "Only PDF files are supported."
        });
        return;
      }

      const file = acceptedFiles[0];
      if (!file) {
        return;
      }

      beginUpload(file);
    },
    [apiConfigured, beginUpload]
  );

  const resetState = useCallback(() => {
    stopPolling();
    setState(initialState);
    setHasTouched(false);
  }, [stopPolling]);

  const dropzoneDisabled =
    !apiConfigured ||
    state.phase === "uploading" ||
    state.phase === "processing";

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled: dropzoneDisabled,
    onDrop: handleDrop
  });

  const overallStatus = useMemo(() => {
    switch (state.phase) {
      case "uploading":
        return `Uploading${
          state.uploadProgress ? ` • ${state.uploadProgress}%` : ""
        }`;
      case "processing":
        return `Processing${
          state.processingProgress ? ` • ${state.processingProgress}%` : ""
        }`;
      case "completed":
        return "Completed";
      case "error":
        return "Error";
      default:
        return "Idle";
    }
  }, [state.phase, state.processingProgress, state.uploadProgress]);

  const wrapperClassName = ["w-full max-w-xl", className]
    .filter(Boolean)
    .join(" ");

  const baseDropzoneClasses =
    "w-full rounded-xl border-2 border-dashed bg-white/80 p-4 shadow-lg backdrop-blur transition-colors";
  const stateClasses = !apiConfigured
    ? "border-slate-300 opacity-70"
    : isDragActive
    ? "border-blue-500 bg-blue-50"
    : dropzoneDisabled
    ? "border-slate-300 opacity-80"
    : "border-slate-300 hover:border-blue-400";

  return (
    <div className={wrapperClassName}>
      <div
        {...getRootProps({
          className: `${baseDropzoneClasses} ${stateClasses}`,
          "aria-disabled": dropzoneDisabled
        })}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col gap-2 text-center">
          <p className="text-sm font-medium text-slate-700">
            {apiConfigured
              ? "Drag and drop an ACORD PDF here"
              : "Upload API not configured"}
          </p>
          <p className="text-xs text-slate-500">
            {apiConfigured
              ? "Only PDF files are supported. Click to browse."
              : "Set VITE_ACORD_API_BASE_URL (and optional VITE_ACORD_API_TOKEN)."}
          </p>

          {state.fileName && (
            <p className="mt-1 text-xs font-medium text-slate-600">
              {state.fileName}
            </p>
          )}

          {state.phase !== "idle" && (
            <div className="mt-3 space-y-3 text-left">
              <StatusBar label="Upload" value={state.uploadProgress} />
              {state.phase !== "uploading" && (
                <StatusBar
                  label="Processing"
                  value={
                    state.phase === "completed" ? 100 : state.processingProgress
                  }
                />
              )}

              <p
                className={`text-xs ${
                  state.phase === "error"
                    ? "text-red-600"
                    : state.phase === "completed"
                    ? "text-green-600"
                    : "text-slate-600"
                }`}
              >
                {state.error || state.message || overallStatus}
              </p>

              {state.jobId && (
                <p className="text-[11px] font-mono text-slate-500">
                  Job ID: {state.jobId}
                </p>
              )}
            </div>
          )}

          {state.phase !== "uploading" &&
            state.phase !== "processing" &&
            hasTouched && (
              <button
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  resetState();
                }}
                className="mx-auto mt-2 text-xs font-medium text-blue-600 hover:underline"
              >
                Clear
              </button>
            )}
        </div>
      </div>
    </div>
  );
}

interface StatusBarProps {
  label: string;
  value: number;
}

function StatusBar({ label, value }: StatusBarProps) {
  const clampedValue = Math.max(0, Math.min(100, Math.round(value)));

  return (
    <div>
      <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-slate-500">
        <span>{label}</span>
        <span>{clampedValue}%</span>
      </div>
      <div className="mt-1 h-2 w-full rounded-full bg-slate-200">
        <div
          className="h-2 rounded-full bg-blue-500 transition-all"
          style={{ width: `${clampedValue}%` }}
        />
      </div>
    </div>
  );
}
