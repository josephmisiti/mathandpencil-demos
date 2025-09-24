import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileError, FileRejection, useDropzone } from "react-dropzone";
import {
  ProgressResponse,
  fetchProgress,
  uploadPdf,
  useAcordApiConfig
} from "../services/acordApi";

const POLL_INTERVAL_MS = 4000;

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

function createInitialState(): UploadState {
  return { ...initialState };
}

export default function PdfUploadDropzone({
  className,
  onComplete
}: PdfUploadDropzoneProps) {
  const [state, setState] = useState<UploadState>(() => createInitialState());
  const [hasTouched, setHasTouched] = useState(false);
  const pollTimeoutRef = useRef<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  const { baseUrl: apiBaseUrl } = useAcordApiConfig();

  const apiConfigured = useMemo(() => Boolean(apiBaseUrl), [apiBaseUrl]);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      if (pollTimeoutRef.current !== null) {
        window.clearTimeout(pollTimeoutRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const stopPolling = useCallback(() => {
    if (pollTimeoutRef.current !== null) {
      window.clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const updateProcessingState = useCallback(
    (payload: ProgressResponse) => {
      if (!isMountedRef.current) {
        return;
      }

      setState((prev) => {
        const nextProgress =
          typeof payload.progress === "number"
            ? Math.max(0, Math.min(100, payload.progress))
            : prev.processingProgress;

        const baseUpdates: Partial<UploadState> = {
          processingProgress: nextProgress,
          message: payload.message || payload.stage || prev.message,
          result: payload.result ?? prev.result
        };

        if (payload.status === "completed") {
          return {
            ...prev,
            ...baseUpdates,
            phase: "completed",
            processingProgress: 100,
            error: null
          };
        }

        if (payload.status === "failed") {
          return {
            ...prev,
            ...baseUpdates,
            phase: "error",
            error: payload.error || payload.message || "Processing failed."
          };
        }

        return {
          ...prev,
          ...baseUpdates,
          phase: "processing",
          error: null
        };
      });

      if (payload.status === "completed") {
        stopPolling();
        onComplete?.(payload.result ?? null);
      } else if (payload.status === "failed") {
        stopPolling();
      }
    },
    [onComplete, stopPolling]
  );

  const pollJob = useCallback(
    (jobId: string) => {
      const poll = async () => {
        if (!isMountedRef.current) {
          return;
        }

        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
          const response = await fetchProgress(jobId, controller.signal);
          updateProcessingState(response);

          if (!isMountedRef.current) {
            return;
          }

          if (response.status !== "completed" && response.status !== "failed") {
            pollTimeoutRef.current = window.setTimeout(poll, POLL_INTERVAL_MS);
          }
        } catch (error) {
          if (!isMountedRef.current) {
            return;
          }

          if (error instanceof Error && error.name === "AbortError") {
            return;
          }

          stopPolling();
          setState((prev) => ({
            ...prev,
            phase: "error",
            error:
              error instanceof Error
                ? error.message
                : "An unexpected error occurred while polling progress.",
            message: "Processing failed."
          }));
        } finally {
          abortControllerRef.current = null;
        }
      };

      poll();
    },
    [stopPolling, updateProcessingState]
  );

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
        const result = await uploadPdf(file, (progress) => {
          setState((prev) =>
            prev.phase === "uploading"
              ? { ...prev, uploadProgress: progress }
              : prev
          );
        });

        if (!isMountedRef.current) {
          return;
        }

        setState((prev) => ({
          ...prev,
          phase: "processing",
          uploadProgress: 100,
          jobId: result.job_id,
          message: result.message || "Upload complete. Processing..."
        }));

        pollJob(result.job_id);
      } catch (error) {
        if (!isMountedRef.current) {
          return;
        }

        stopPolling();
        setState({
          phase: "error",
          uploadProgress: 0,
          processingProgress: 0,
          message: "Upload failed.",
          error: error instanceof Error ? error.message : String(error),
          jobId: null,
          fileName: file.name,
          result: null
        });
      }
    },
    [pollJob, stopPolling]
  );

  const handleDrop = useCallback(
    (acceptedFiles: File[], rejections: FileRejection[]) => {
      if (!apiConfigured) {
        setState({
          phase: "error",
          uploadProgress: 0,
          processingProgress: 0,
          message: "",
          error:
            "Upload API is not configured. Set VITE_ACORD_API_BASE_URL in your environment.",
          jobId: null,
          fileName: null,
          result: null
        });
        return;
      }

      if (rejections.length > 0) {
        const messages = rejections
          .flatMap((item) => item.errors.map((error: FileError) => error.message))
          .join("; ");
        setState({
          phase: "error",
          uploadProgress: 0,
          processingProgress: 0,
          message: "",
          error: messages || "Only PDF files are supported.",
          jobId: null,
          fileName: null,
          result: null
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
    setState(createInitialState());
    setHasTouched(false);
  }, [stopPolling]);

  const dropzoneDisabled = !apiConfigured || state.phase === "uploading" || state.phase === "processing";

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled: dropzoneDisabled,
    onDrop: handleDrop
  });

  const overallStatus = useMemo(() => {
    switch (state.phase) {
      case "uploading":
        return `Uploading${state.uploadProgress ? ` • ${state.uploadProgress}%` : ""}`;
      case "processing":
        return `Processing${state.processingProgress ? ` • ${state.processingProgress}%` : ""}`;
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

          {state.phase !== "uploading" && state.phase !== "processing" && hasTouched && (
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
