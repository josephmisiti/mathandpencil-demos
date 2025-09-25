import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import html2canvas from "html2canvas";
import DrawingCanvas from "./DrawingCanvas";
import {
  RoofAnalysisResult,
  fetchRoofAnalysisProgress,
  startRoofAnalysis,
  useRoofAnalysisApiConfig
} from "../services/roofAnalysisApi";
import { createPortal } from "react-dom";

interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface RoofAnalysisProps {
  active: boolean;
  mapContainerRef: React.RefObject<HTMLDivElement | null>;
  onExit: () => void;
  panelContainerRef?: React.RefObject<HTMLDivElement | null>;
}

type JobPhase =
  | "idle"
  | "capturing"
  | "queued"
  | "processing"
  | "completed"
  | "error";

interface JobState {
  phase: JobPhase;
  progress: number;
  message: string;
  stage: string | null;
  jobId: string | null;
  error: string | null;
  result: RoofAnalysisResult | null;
  lastUpdated: number | null;
}

const initialJobState: JobState = {
  phase: "idle",
  progress: 0,
  message: "",
  stage: null,
  jobId: null,
  error: null,
  result: null,
  lastUpdated: null
};

const PROGRESS_POLL_INTERVAL = 2500;

const normalizeProgress = (value: number | undefined, fallback: number) => {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
}

  if (value <= 1 && value >= 0) {
    return Math.round(value * 100);
  }

  return Math.round(Math.max(0, Math.min(100, value)));
};

const formatLabel = (label: string | null | undefined) => {
  if (!label) return "";
  return label
    .split(/[_-]/)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
};

const renderBadgeList = (items?: string[]) => {
  if (!items || items.length === 0) {
    return <span className="text-slate-400">None noted</span>;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700"
        >
          {item}
        </span>
      ))}
    </div>
  );
};

const RoofAnalysis: React.FC<RoofAnalysisProps> = ({
  active,
  mapContainerRef,
  onExit,
  panelContainerRef
}) => {
  const [selectedBounds, setSelectedBounds] = useState<Bounds | null>(null);
  const [jobState, setJobState] = useState<JobState>(initialJobState);
  const pollIntervalRef = useRef<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { baseUrl: apiBaseUrl, hasToken } = useRoofAnalysisApiConfig();
  const apiConfigured = useMemo(() => Boolean(apiBaseUrl), [apiBaseUrl]);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const resetAnalysis = useCallback(() => {
    stopPolling();
    setJobState(initialJobState);
    setSelectedBounds(null);
  }, [stopPolling]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();

      const poll = async () => {
        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
          const progressData = await fetchRoofAnalysisProgress(
            jobId,
            controller.signal
          );

          const nextPhase: JobPhase = (() => {
            switch (progressData.status) {
              case "queued":
                return "queued";
              case "processing":
                return "processing";
              case "completed":
                return "completed";
              case "failed":
                return "error";
              default:
                return "processing";
            }
          })();

          setJobState((prev) => ({
            ...prev,
            phase: nextPhase,
            jobId,
            progress: normalizeProgress(progressData.progress, prev.progress),
            message: progressData.message || prev.message,
            stage: progressData.stage || prev.stage,
            error: progressData.error || null,
            result: progressData.result ?? prev.result,
            lastUpdated: Date.now()
          }));

          if (progressData.status === "completed" || progressData.status === "failed") {
            stopPolling();
          }
        } catch (error) {
          stopPolling();
          setJobState((prev) => ({
            ...prev,
            phase: "error",
            error:
              error instanceof Error
                ? error.message
                : "Roof analysis progress failed",
            message: "Roof analysis progress failed",
            lastUpdated: Date.now()
          }));
        }
      };

      poll();
      pollIntervalRef.current = window.setInterval(poll, PROGRESS_POLL_INTERVAL);
    },
    [stopPolling]
  );

  const handleDrawComplete = useCallback(
    async (bounds: Bounds) => {
      if (!apiConfigured) {
        setJobState({
          ...initialJobState,
          phase: "error",
          error:
            "Roof analysis API is not configured. Set VITE_ROOF_ANALYSIS_API_BASE_URL.",
          message: "Roof analysis API not configured"
        });
        return;
      }

      if (!hasToken) {
        setJobState({
          ...initialJobState,
          phase: "error",
          error:
            "Missing roof analysis API token. Set VITE_ROOF_ANALYSIS_API_TOKEN.",
          message: "Missing API token"
        });
        return;
      }

      if (!mapContainerRef.current) {
        setJobState({
          ...initialJobState,
          phase: "error",
          error: "Map view is not ready for capture.",
          message: "Map is not ready"
        });
        return;
      }

      const mapElement = mapContainerRef.current.querySelector(
        ".gm-style"
      ) as HTMLElement | null;
      if (!mapElement) {
        setJobState({
          ...initialJobState,
          phase: "error",
          error: "Unable to locate the Google Maps canvas for capture.",
          message: "Google Maps element not found"
        });
        return;
      }

      stopPolling();
      setSelectedBounds(bounds);
      setJobState({
        phase: "capturing",
        progress: 10,
        message: "Capturing roof selection...",
        stage: "capturing",
        jobId: null,
        error: null,
        result: null,
        lastUpdated: Date.now()
      });

      const containerRect = mapContainerRef.current.getBoundingClientRect();
      const mapRect = mapElement.getBoundingClientRect();
      const offsetX = mapRect.left - containerRect.left;
      const offsetY = mapRect.top - containerRect.top;

      const captureBounds = {
        x: bounds.x - offsetX,
        y: bounds.y - offsetY,
        width: bounds.width,
        height: bounds.height
      };

      const clampStartX = Math.min(Math.max(0, captureBounds.x), mapRect.width);
      const clampStartY = Math.min(Math.max(0, captureBounds.y), mapRect.height);
      const clampEndX = Math.min(
        Math.max(0, captureBounds.x + captureBounds.width),
        mapRect.width
      );
      const clampEndY = Math.min(
        Math.max(0, captureBounds.y + captureBounds.height),
        mapRect.height
      );

      const clampedBounds = {
        x: clampStartX,
        y: clampStartY,
        width: clampEndX - clampStartX,
        height: clampEndY - clampStartY
      };

      if (clampedBounds.width <= 0 || clampedBounds.height <= 0) {
        setJobState({
          ...initialJobState,
          phase: "error",
          error: "Selection must stay within the map view. Please try again.",
          message: "Selection outside map bounds"
        });
        return;
      }

      try {
        const canvas = await html2canvas(mapElement, {
          useCORS: true,
          backgroundColor: null,
          x: clampedBounds.x,
          y: clampedBounds.y,
          width: clampedBounds.width,
          height: clampedBounds.height,
          scrollX: window.scrollX,
          scrollY: window.scrollY
        });

        const imageData = canvas.toDataURL("image/png");

        setJobState((prev) => ({
          ...prev,
          phase: "queued",
          progress: 15,
          message: "Submitting selection to roof analysis service...",
          stage: "queued",
          lastUpdated: Date.now()
        }));

        const startResponse = await startRoofAnalysis(imageData);

        setJobState((prev) => ({
          ...prev,
          phase: startResponse.status === "queued" ? "queued" : "processing",
          progress: 20,
          message:
            startResponse.message || "Image queued for roof analysis",
          stage: startResponse.status || "queued",
          jobId: startResponse.job_id,
          error: null,
          lastUpdated: Date.now()
        }));

        startPolling(startResponse.job_id);
      } catch (error) {
        stopPolling();
        setJobState({
          ...initialJobState,
          phase: "error",
          error:
            error instanceof Error
              ? error.message
              : "Unknown error while processing roof analysis.",
          message: "Roof analysis failed"
        });
      }
    },
    [
      apiConfigured,
      hasToken,
      mapContainerRef,
      startPolling,
      stopPolling
    ]
  );

  const roofAnalysis = jobState.result?.analysis?.roof_analysis;
  const drawingDisabled =
    !apiConfigured ||
    !hasToken ||
    jobState.phase === "capturing" ||
    jobState.phase === "queued" ||
    jobState.phase === "processing";

  if (!active) {
    return null;
  }

  const progressPercent = Math.max(0, Math.min(100, jobState.progress));
  const panelBody = (
    <div className="rounded-lg border border-slate-200 bg-white/95 p-4 shadow-xl backdrop-blur">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-900">
              Roof analysis mode
            </h3>
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              Satellite view
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-600">
            Click and drag on the map to draw a bounding box around the
            roof. The selected area will be captured and sent to the roof
            analysis service.
          </p>
        </div>
        <button
          type="button"
          className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
          onClick={() => {
            resetAnalysis();
            onExit();
          }}
        >
          Close
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-600">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          Drag to draw selection
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-slate-500" />
          ESC to exit
        </span>
      </div>

      {!apiConfigured && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          Roof analysis API base URL is not configured.
        </div>
      )}

      {apiConfigured && !hasToken && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          Roof analysis API token is missing.
        </div>
      )}

      {(jobState.phase === "capturing" ||
        jobState.phase === "queued" ||
        jobState.phase === "processing") && (
        <div className="mt-3 rounded-md border border-blue-200 bg-blue-50 px-3 py-3">
          <div className="flex items-center justify-between text-xs font-medium text-blue-900">
            <span>{jobState.message || "Processing roof analysis"}</span>
            <span>{progressPercent}%</span>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded bg-blue-100">
            <div
              className="h-full bg-blue-500 transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          {jobState.stage && (
            <div className="mt-2 text-xs text-blue-700">
              Current stage: {formatLabel(jobState.stage)}
            </div>
          )}
        </div>
      )}

      {jobState.error && (
        <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {jobState.error}
        </div>
      )}

      {roofAnalysis && jobState.phase === "completed" && (
        <div className="mt-4 space-y-4">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
            <div className="text-sm font-semibold text-emerald-800">
              Roof analysis completed
            </div>
            <div className="mt-1 text-sm text-emerald-900">
              Model: {jobState.result?.model_id}
            </div>
            {jobState.lastUpdated && (
              <div className="text-xs text-emerald-700">
                Updated {new Date(jobState.lastUpdated).toLocaleTimeString()}
              </div>
            )}
          </div>

          {roofAnalysis.quality && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">
                Quality assessment
              </header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Overall rating</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.quality.overall_rating || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Condition score</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.quality.condition_score ?? "—"}
                  </span>
                </div>
                <div>
                  <div className="text-slate-500">Visible issues</div>
                  <div className="mt-1">{renderBadgeList(roofAnalysis.quality.visible_issues)}</div>
                </div>
                <div>
                  <div className="text-slate-500">Quality indicators</div>
                  <div className="mt-1">{renderBadgeList(roofAnalysis.quality.quality_indicators)}</div>
                </div>
                {roofAnalysis.quality.analysis_reasoning && (
                  <p className="text-sm text-slate-600">
                    {roofAnalysis.quality.analysis_reasoning}
                  </p>
                )}
              </div>
            </section>
          )}

          {roofAnalysis.age && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">
                Age estimation
              </header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Estimated age</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.age.estimated_age_years || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Age category</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.age.age_category || "—"}
                  </span>
                </div>
                <div>
                  <div className="text-slate-500">Weathering indicators</div>
                  <div className="mt-1">{renderBadgeList(roofAnalysis.age.weathering_indicators)}</div>
                </div>
                {roofAnalysis.age.analysis_reasoning && (
                  <p className="text-sm text-slate-600">
                    {roofAnalysis.age.analysis_reasoning}
                  </p>
                )}
              </div>
            </section>
          )}

          {roofAnalysis.shape && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">
                Shape analysis
              </header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Primary shape</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.shape.primary_shape || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Complexity</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.shape.complexity || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Roof planes</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.shape.roof_planes ?? "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Pitch</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.shape.pitch_estimate || "—"}
                  </span>
                </div>
                <div>
                  <div className="text-slate-500">Architectural features</div>
                  <div className="mt-1">{renderBadgeList(roofAnalysis.shape.architectural_features)}</div>
                </div>
                {roofAnalysis.shape.analysis_reasoning && (
                  <p className="text-sm text-slate-600">
                    {roofAnalysis.shape.analysis_reasoning}
                  </p>
                )}
              </div>
            </section>
          )}

          {roofAnalysis.cover && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">
                Cover material
              </header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Material type</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.cover.material_type || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Confidence</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.cover.material_confidence || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Color</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.cover.color_description || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Texture</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.cover.texture_pattern || "—"}
                  </span>
                </div>
                <div>
                  <div className="text-slate-500">Secondary materials</div>
                  <div className="mt-1">{renderBadgeList(roofAnalysis.cover.secondary_materials)}</div>
                </div>
                {roofAnalysis.cover.analysis_reasoning && (
                  <p className="text-sm text-slate-600">
                    {roofAnalysis.cover.analysis_reasoning}
                  </p>
                )}
              </div>
            </section>
          )}

          {roofAnalysis.overall_assessment && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">
                Overall assessment
              </header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                {roofAnalysis.overall_assessment.summary && (
                  <p className="text-sm text-slate-900">
                    {roofAnalysis.overall_assessment.summary}
                  </p>
                )}
                <div>
                  <div className="text-slate-500">Recommendations</div>
                  <div className="mt-1">{renderBadgeList(roofAnalysis.overall_assessment.recommendations)}</div>
                </div>
                <div>
                  <div className="text-slate-500">Limitations</div>
                  <div className="mt-1">{renderBadgeList(roofAnalysis.overall_assessment.analysis_limitations)}</div>
                </div>
              </div>
            </section>
          )}

          {roofAnalysis.image_analysis_metadata && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">
                Image metadata
              </header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Image quality</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.image_analysis_metadata.image_quality || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Viewing angle</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.image_analysis_metadata.viewing_angle || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Resolution</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.image_analysis_metadata.resolution_adequacy || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Weather</span>
                  <span className="font-medium text-slate-900">
                    {roofAnalysis.image_analysis_metadata.weather_conditions || "—"}
                  </span>
                </div>
              </div>
            </section>
          )}

          {jobState.result?.artifacts && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">
                Artifacts
              </header>
              <div className="mt-3 space-y-1 text-xs text-slate-600">
                {jobState.result.artifacts.image_path && (
                  <div>
                    <span className="font-medium text-slate-700">Image:</span>{" "}
                    <code className="break-all text-slate-500">
                      {jobState.result.artifacts.image_path}
                    </code>
                  </div>
                )}
                {jobState.result.artifacts.analysis_path && (
                  <div>
                    <span className="font-medium text-slate-700">Analysis:</span>{" "}
                    <code className="break-all text-slate-500">
                      {jobState.result.artifacts.analysis_path}
                    </code>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {(jobState.phase === "completed" || jobState.phase === "error") && (
          <button
            type="button"
            className="rounded border border-slate-200 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50"
            onClick={resetAnalysis}
          >
            Clear analysis
          </button>
        )}
        {selectedBounds && jobState.phase !== "capturing" &&
          jobState.phase !== "queued" &&
          jobState.phase !== "processing" && (
            <button
              type="button"
              className="rounded border border-slate-200 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50"
              onClick={resetAnalysis}
            >
              Draw again
            </button>
          )}
      </div>
    </div>
  );

  let panelNode: React.ReactNode;
  if (panelContainerRef?.current) {
    panelNode = createPortal(
      <div className="space-y-4">{panelBody}</div>,
      panelContainerRef.current
    );
  } else {
    panelNode = (
      <div className="pointer-events-none absolute left-1/2 top-4 z-40 w-full max-w-xl -translate-x-1/2 px-4">
        <div className="pointer-events-auto">{panelBody}</div>
      </div>
    );
  }

  return (
    <>
      <div className="absolute inset-0 z-30 flex flex-col" aria-live="polite">
        <DrawingCanvas
          onDrawComplete={handleDrawComplete}
          disabled={drawingDisabled}
          highlight={selectedBounds}
        />
      </div>
      {panelNode}
    </>
  );
};

export default RoofAnalysis;
