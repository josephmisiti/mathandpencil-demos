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
  ConstructionAnalysisResult,
  downloadConstructionAnalysisReport,
  fetchConstructionAnalysisProgress,
  startConstructionAnalysis,
  useConstructionAnalysisApiConfig
} from "../services/constructionAnalysisApi";
import { createPortal } from "react-dom";

interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ConstructionAnalysisProps {
  overlayActive: boolean;
  visible: boolean;
  mapContainerRef: React.RefObject<HTMLDivElement | null>;
  onExit: () => void;
  panelContainerRef?: React.RefObject<HTMLDivElement | null>;
  onOverlayCancel?: () => void;
  onRequestDraw?: () => void;
  isStreetViewVisible: boolean;
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
  result: ConstructionAnalysisResult | null;
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

const PIPELINE_STAGES = [
  {
    id: "upload",
    label: "Upload image",
    matches: ["capturing", "uploaded", "received", "image_saved"]
  },
  {
    id: "analysis",
    label: "AI analysis",
    matches: ["invoking_model", "parsing_response"]
  },
  {
    id: "report",
    label: "Generate report",
    matches: ["analysis_complete", "report_generation"]
  },
  {
    id: "complete",
    label: "Report ready",
    matches: ["finished"]
  }
] as const;

type PipelineStageId = (typeof PIPELINE_STAGES)[number]["id"];
type PipelineStageStatus = "pending" | "active" | "done" | "failed";

const STAGE_ERROR_MAP: Record<string, PipelineStageId> = {
  decode_error: "upload",
  empty_response: "analysis",
  json_parse_error: "analysis",
  report_generation_error: "report",
  error: "analysis"
};

const PIPELINE_INDICATOR_CLASS: Record<PipelineStageStatus, string> = {
  done: "bg-emerald-500",
  active: "bg-blue-500 animate-pulse",
  pending: "bg-slate-300",
  failed: "bg-rose-500"
};

const PIPELINE_TEXT_CLASS: Record<PipelineStageStatus, string> = {
  done: "text-emerald-700",
  active: "text-blue-900 font-medium",
  pending: "text-slate-500",
  failed: "text-rose-600 font-semibold"
};

const resolvePipelineStageId = (stage: string | null): PipelineStageId | null => {
  if (!stage) {
    return null;
  }

  if (STAGE_ERROR_MAP[stage]) {
    return STAGE_ERROR_MAP[stage];
  }

  for (const entry of PIPELINE_STAGES) {
    if (entry.matches.includes(stage)) {
      return entry.id;
    }
  }

  return null;
};

const derivePipelineStatuses = (
  stage: string | null,
  phase: JobPhase
): PipelineStageStatus[] => {
  const stageId = resolvePipelineStageId(stage);
  const activeIndex = stageId
    ? PIPELINE_STAGES.findIndex((entry) => entry.id === stageId)
    : -1;
  const isFailed = phase === "error";

  return PIPELINE_STAGES.map((entry, index) => {
    if (phase === "completed") {
      return "done";
    }

    if (isFailed && activeIndex === index) {
      return "failed";
    }

    if (activeIndex === -1) {
      const hasStarted = phase !== "idle";
      return hasStarted && index === 0 ? "active" : "pending";
    }

    if (index < activeIndex) {
      return "done";
    }

    if (index === activeIndex) {
      return isFailed ? "failed" : "active";
    }

    return "pending";
  });
};

const formatLabel = (label: string | null | undefined) => {
  if (!label) return "";
  return label
    .split(/[_-]/)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
};

const renderBadgeList = (items?: string[] | null) => {
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

const ConstructionAnalysis: React.FC<ConstructionAnalysisProps> = ({
  overlayActive,
  visible,
  mapContainerRef,
  onExit,
  panelContainerRef,
  onOverlayCancel,
  onRequestDraw,
  isStreetViewVisible
}) => {
  const [selectedBounds, setSelectedBounds] = useState<Bounds | null>(null);
  const [jobState, setJobState] = useState<JobState>(initialJobState);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const pollIntervalRef = useRef<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { baseUrl: apiBaseUrl, hasToken } = useConstructionAnalysisApiConfig();
  const apiConfigured = useMemo(() => Boolean(apiBaseUrl), [apiBaseUrl]);
  const pipelineStatuses = useMemo(
    () => derivePipelineStatuses(jobState.stage, jobState.phase),
    [jobState.stage, jobState.phase]
  );

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
    setDownloadError(null);
    setDownloadingReport(false);
  }, [stopPolling]);

  const cancelDrawingOnly = useCallback(() => {
    stopPolling();
    setJobState((prev) => ({
      ...prev,
      phase: prev.result ? "completed" : "idle",
      progress: prev.result ? 100 : 0,
      message: prev.result ? "Construction analysis ready" : "",
      stage: prev.result ? prev.stage : null,
      jobId: null,
      error: null
    }));
    setSelectedBounds(null);
    onOverlayCancel?.();
  }, [stopPolling, onOverlayCancel]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  useEffect(() => {
    setDownloadError(null);
    setDownloadingReport(false);
  }, [jobState.jobId]);

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();

      const poll = async () => {
        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
          const progressData = await fetchConstructionAnalysisProgress(
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
                : "Construction analysis progress failed",
            message: "Construction analysis progress failed",
            lastUpdated: Date.now()
          }));
        }
      };

      poll();
      pollIntervalRef.current = window.setInterval(poll, PROGRESS_POLL_INTERVAL);
    },
    [stopPolling]
  );

  const handleReportDownload = useCallback(async () => {
    if (!jobState.jobId) {
      return;
    }

    setDownloadError(null);
    setDownloadingReport(true);

    try {
      const { blob, filename } = await downloadConstructionAnalysisReport(jobState.jobId);
      const blobUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = blobUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      setDownloadError(
        error instanceof Error
          ? error.message
          : "Failed to download construction analysis report."
      );
    } finally {
      setDownloadingReport(false);
    }
  }, [jobState.jobId]);

  const handleDrawComplete = useCallback(
    async (bounds: Bounds) => {
      if (!apiConfigured) {
        setJobState({
          ...initialJobState,
          phase: "error",
          error:
            "Construction analysis API is not configured. Set VITE_CONSTRUCTION_ANALYSIS_API_BASE_URL.",
          message: "Construction analysis API not configured"
        });
        return;
      }

      if (!hasToken) {
        setJobState({
          ...initialJobState,
          phase: "error",
          error:
            "Missing construction analysis API token. Set VITE_CONSTRUCTION_ANALYSIS_API_TOKEN.",
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
      setDownloadError(null);
      setDownloadingReport(false);
      setSelectedBounds(bounds);
      setJobState({
        phase: "capturing",
        progress: 10,
        message: "Capturing building selection...",
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
          message: "Submitting selection to construction analysis service...",
          stage: "queued",
          lastUpdated: Date.now()
        }));

        const startResponse = await startConstructionAnalysis(imageData);

        setJobState((prev) => ({
          ...prev,
          phase: startResponse.status === "queued" ? "queued" : "processing",
          progress: 20,
          message:
            startResponse.message || "Image queued for construction analysis",
          stage: startResponse.status || "queued",
          jobId: startResponse.job_id,
          error: null,
          lastUpdated: Date.now()
        }));

        onOverlayCancel?.();
        startPolling(startResponse.job_id);
      } catch (error) {
        stopPolling();
        setJobState({
          ...initialJobState,
          phase: "error",
          error:
            error instanceof Error
              ? error.message
              : "Unknown error while processing construction analysis.",
          message: "Construction analysis failed"
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

  const buildingAnalysis = jobState.result?.analysis?.building_analysis;

  useEffect(() => {
    if (overlayActive && !isStreetViewVisible) {
      cancelDrawingOnly();
    }
  }, [overlayActive, isStreetViewVisible, cancelDrawingOnly]);

  const previousOverlayRef = useRef(overlayActive);
  useEffect(() => {
    if (previousOverlayRef.current && !overlayActive && jobState.phase === "capturing") {
      cancelDrawingOnly();
    }
    previousOverlayRef.current = overlayActive;
  }, [overlayActive, cancelDrawingOnly, jobState.phase]);

  const drawingDisabled =
    !apiConfigured ||
    !hasToken ||
    !isStreetViewVisible ||
    jobState.phase === "queued" ||
    jobState.phase === "processing";

  if (!overlayActive && !visible) {
    return null;
  }

  const progressPercent = Math.max(0, Math.min(100, jobState.progress));
  const panelBody = (
    <div className="rounded-lg border border-slate-200 bg-white/95 p-4 shadow-xl backdrop-blur">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-900">
              Construction analysis mode
            </h3>
          </div>
          <p className="mt-1 text-sm text-slate-600">
            Click and drag on the map to draw a bounding box around the visible face of the building. The selected image will be captured and sent to the construction analysis service.
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
          Construction analysis API base URL is not configured.
        </div>
      )}

      {apiConfigured && !hasToken && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          Construction analysis API token is missing.
        </div>
      )}

      {apiConfigured && hasToken && !isStreetViewVisible && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          Enter Street View to draw a new bounding box.
        </div>
      )}

      {(jobState.phase === "capturing" ||
        jobState.phase === "queued" ||
        jobState.phase === "processing" ||
        jobState.phase === "error") && (
        <div className="mt-3 rounded-md border border-blue-200 bg-blue-50 px-3 py-3">
          <div className="flex items-center justify-between text-xs font-medium text-blue-900">
            <span>{jobState.message || "Processing construction analysis"}</span>
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
          <div className="mt-3 space-y-1">
            {PIPELINE_STAGES.map((pipelineStage, index) => {
              const status = pipelineStatuses[index] ?? "pending";
              return (
                <div key={pipelineStage.id} className="flex items-center gap-2 text-xs">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${PIPELINE_INDICATOR_CLASS[status]}`}
                  />
                  <span className={PIPELINE_TEXT_CLASS[status]}>
                    {pipelineStage.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {jobState.error && (
        <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {jobState.error}
        </div>
      )}

      {buildingAnalysis && jobState.phase === "completed" && (
        <div className="mt-4 space-y-4">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
            <div className="text-sm font-semibold text-emerald-800">
              Construction analysis completed
            </div>
            <div className="mt-1 text-sm text-emerald-900">
              Model: {jobState.result?.model_id}
            </div>
            {jobState.lastUpdated && (
              <div className="text-xs text-emerald-700">
                Updated {new Date(jobState.lastUpdated).toLocaleTimeString()}
              </div>
            )}
            {jobState.result?.report_generated_at && (
              <div className="text-xs text-emerald-700">
                Report generated {new Date(jobState.result.report_generated_at).toLocaleString()}
              </div>
            )}
          </div>

          {jobState.result?.artifacts && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">Artifacts</header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
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
                {(() => {
                  const artifacts = jobState.result?.artifacts;
                  const reportPath = artifacts?.report_absolute_path || artifacts?.report_path;
                  if (!reportPath) {
                    return null;
                  }
                  return (
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="min-w-0 flex-1">
                        <span className="font-medium text-slate-700">Report:</span>{" "}
                        <code className="break-all text-slate-500">{reportPath}</code>
                      </div>
                      <button
                        type="button"
                        className="rounded border border-emerald-200 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={handleReportDownload}
                        disabled={downloadingReport}
                      >
                        {downloadingReport ? "Preparing download..." : "Download PDF"}
                      </button>
                    </div>
                  );
                })()}
              </div>
              {downloadError && (
                <div className="mt-2 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-600">
                  {downloadError}
                </div>
              )}
            </section>
          )}

          {(() => {
            type SectionDefinition = {
              title: string;
              section: unknown;
              pairs: [string, string | number | undefined][];
              listFields: [string, string[] | undefined][];
              reasoning?: string;
            };
            const sectionRows: SectionDefinition[] = [
              {
                title: "Construction type",
                section: buildingAnalysis.construction_type,
                pairs: [
                  ["Primary structural system", buildingAnalysis.construction_type?.primary_structural_system],
                  ["Wall construction", buildingAnalysis.construction_type?.wall_construction],
                  ["Construction class", buildingAnalysis.construction_type?.construction_class],
                  ["AIR construction code", buildingAnalysis.construction_type?.air_construction_code],
                  ["Confidence", buildingAnalysis.construction_type?.construction_confidence]
                ],
                listFields: [
                  ["Structural indicators", buildingAnalysis.construction_type?.structural_indicators]
                ],
                reasoning: buildingAnalysis.construction_type?.analysis_reasoning
              },
              {
                title: "Occupancy assessment",
                section: buildingAnalysis.occupancy_assessment,
                pairs: [
                  ["Primary use", buildingAnalysis.occupancy_assessment?.primary_use],
                  ["AIR occupancy code", buildingAnalysis.occupancy_assessment?.air_occupancy_code],
                  ["ISO occupancy type", buildingAnalysis.occupancy_assessment?.iso_occupancy_type],
                  ["Confidence", buildingAnalysis.occupancy_assessment?.occupancy_confidence]
                ],
                listFields: [
                  ["Secondary uses", buildingAnalysis.occupancy_assessment?.secondary_uses],
                  ["Use indicators", buildingAnalysis.occupancy_assessment?.use_indicators]
                ],
                reasoning: buildingAnalysis.occupancy_assessment?.analysis_reasoning
              },
              {
                title: "Physical characteristics",
                section: buildingAnalysis.physical_characteristics,
                pairs: [
                  ["Story count", buildingAnalysis.physical_characteristics?.story_count],
                  ["Estimated height (ft)", buildingAnalysis.physical_characteristics?.estimated_height_feet],
                  ["Facade width estimate", buildingAnalysis.physical_characteristics?.building_width_estimate],
                  ["Architectural style", buildingAnalysis.physical_characteristics?.architectural_style]
                ],
                listFields: [
                  ["Notable features", buildingAnalysis.physical_characteristics?.notable_features],
                  ["Accessibility features", buildingAnalysis.physical_characteristics?.accessibility_features]
                ],
                reasoning: buildingAnalysis.physical_characteristics?.analysis_reasoning
              },
              {
                title: "Construction materials",
                section: buildingAnalysis.construction_materials,
                pairs: [
                  ["Primary wall material", buildingAnalysis.construction_materials?.primary_wall_material],
                  ["Window type", buildingAnalysis.construction_materials?.window_type],
                  ["Material quality", buildingAnalysis.construction_materials?.material_quality],
                  ["Visible roof material", buildingAnalysis.construction_materials?.visible_roof_material],
                  ["Material condition", buildingAnalysis.construction_materials?.material_condition]
                ],
                listFields: [
                  ["Secondary materials", buildingAnalysis.construction_materials?.secondary_materials]
                ],
                reasoning: buildingAnalysis.construction_materials?.analysis_reasoning
              },
              {
                title: "Risk factors",
                section: buildingAnalysis.risk_factors,
                pairs: [
                  ["Fire risk level", buildingAnalysis.risk_factors?.fire_risk_level],
                  ["Security level", buildingAnalysis.risk_factors?.security_level],
                  ["Overall risk profile", buildingAnalysis.risk_factors?.overall_risk_profile]
                ],
                listFields: [
                  ["Nat cat vulnerabilities", buildingAnalysis.risk_factors?.nat_cat_vulnerabilities],
                  ["Proximity hazards", buildingAnalysis.risk_factors?.proximity_hazards],
                  ["Environmental factors", buildingAnalysis.risk_factors?.environmental_factors]
                ],
                reasoning: buildingAnalysis.risk_factors?.analysis_reasoning
              },
              {
                title: "Age & condition",
                section: buildingAnalysis.age_condition,
                pairs: [
                  ["Estimated age range", buildingAnalysis.age_condition?.estimated_age_range],
                  ["Condition rating", buildingAnalysis.age_condition?.condition_rating],
                  ["Condition score", buildingAnalysis.age_condition?.condition_score],
                  ["Maintenance level", buildingAnalysis.age_condition?.maintenance_level]
                ],
                listFields: [
                  ["Renovation indicators", buildingAnalysis.age_condition?.renovation_indicators],
                  ["Deterioration signs", buildingAnalysis.age_condition?.deterioration_signs]
                ],
                reasoning: buildingAnalysis.age_condition?.analysis_reasoning
              },
              {
                title: "Insurance classifications",
                section: buildingAnalysis.insurance_classifications,
                pairs: [
                  ["Suggested AIR construction", buildingAnalysis.insurance_classifications?.suggested_air_construction],
                  ["Suggested AIR occupancy", buildingAnalysis.insurance_classifications?.suggested_air_occupancy],
                  ["ISO occupancy type", buildingAnalysis.insurance_classifications?.iso_occupancy_type],
                  ["RMS codes", buildingAnalysis.insurance_classifications?.rms_codes],
                  ["Classification confidence", buildingAnalysis.insurance_classifications?.classification_confidence]
                ],
                listFields: [
                  ["Alternative codes", buildingAnalysis.insurance_classifications?.alternative_codes]
                ],
                reasoning: buildingAnalysis.insurance_classifications?.analysis_reasoning
              },
              {
                title: "Underwriting considerations",
                section: buildingAnalysis.underwriting_considerations,
                pairs: [],
                listFields: [
                  ["Key strengths", buildingAnalysis.underwriting_considerations?.key_strengths],
                  ["Key concerns", buildingAnalysis.underwriting_considerations?.key_concerns],
                  ["Recommended inspections", buildingAnalysis.underwriting_considerations?.recommended_inspections],
                  ["Coverage considerations", buildingAnalysis.underwriting_considerations?.coverage_considerations],
                  ["Pricing factors", buildingAnalysis.underwriting_considerations?.pricing_factors]
                ]
              }
            ];

            return sectionRows
              .filter((entry) => Boolean(entry.section))
              .map((entry) => (
                <section key={entry.title} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                  <header className="text-sm font-semibold text-slate-900">{entry.title}</header>
                  <div className="mt-3 space-y-2 text-sm text-slate-700">
                    {entry.pairs
                      .filter(([, value]) => value !== undefined && value !== null && value !== "")
                      .map(([label, value]) => {
                        const displayValue =
                          value === undefined || value === null || value === ""
                            ? "—"
                            : value;
                        return (
                          <div key={label} className="flex items-start justify-between gap-3">
                            <span className="text-slate-500">{label}</span>
                            <span className="font-medium text-slate-900 text-right">
                              {displayValue}
                            </span>
                          </div>
                        );
                      })}
                    {entry.listFields.map(([label, values]) => (
                      <div key={label}>
                        <div className="text-slate-500">{label}</div>
                        <div className="mt-1">{renderBadgeList(values)}</div>
                      </div>
                    ))}
                    {entry.reasoning && (
                      <p className="text-sm text-slate-600">{entry.reasoning}</p>
                    )}
                  </div>
                </section>
              ));
          })()}

          {buildingAnalysis.overall_assessment && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">Overall assessment</header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <div>
                  <div className="text-slate-500">Property summary</div>
                  <p className="mt-1 text-slate-700">{buildingAnalysis.overall_assessment.property_summary || "—"}</p>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Insurability</span>
                  <span className="font-medium text-slate-900">
                    {buildingAnalysis.overall_assessment.insurability || "—"}
                  </span>
                </div>
                <div>
                  <div className="text-slate-500">Key recommendations</div>
                  <div className="mt-1">{renderBadgeList(buildingAnalysis.overall_assessment.key_recommendations)}</div>
                </div>
                <div>
                  <div className="text-slate-500">Analysis limitations</div>
                  <div className="mt-1">{renderBadgeList(buildingAnalysis.overall_assessment.analysis_limitations)}</div>
                </div>
              </div>
            </section>
          )}

          {buildingAnalysis.image_analysis_metadata && (
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <header className="text-sm font-semibold text-slate-900">Image metadata</header>
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Photo quality</span>
                  <span className="font-medium text-slate-900">
                    {buildingAnalysis.image_analysis_metadata.photo_quality || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Viewing angle</span>
                  <span className="font-medium text-slate-900">
                    {buildingAnalysis.image_analysis_metadata.viewing_angle || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Lighting conditions</span>
                  <span className="font-medium text-slate-900">
                    {buildingAnalysis.image_analysis_metadata.lighting_conditions || "—"}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-500">Distance from building</span>
                  <span className="font-medium text-slate-900">
                    {buildingAnalysis.image_analysis_metadata.distance_from_building || "—"}
                  </span>
                </div>
                <div>
                  <div className="text-slate-500">Obstructions</div>
                  <div className="mt-1">{renderBadgeList(buildingAnalysis.image_analysis_metadata.obstructions)}</div>
                </div>
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
        <button
          type="button"
          className="rounded border border-slate-200 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
          onClick={() => {
            resetAnalysis();
            onRequestDraw?.();
          }}
          disabled={drawingDisabled}
        >
          {buildingAnalysis ? "Draw again" : "Start drawing"}
        </button>
      </div>
    </div>
  );

  let panelNode: React.ReactNode;
  if (panelContainerRef?.current) {
    panelNode = createPortal(
      <div className="space-y-4 max-h-full overflow-y-auto pr-1">{panelBody}</div>,
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
      {overlayActive && (
        <div className="absolute inset-0 z-30 flex flex-col" aria-live="polite">
          <DrawingCanvas
            onDrawComplete={handleDrawComplete}
            disabled={drawingDisabled}
            highlight={selectedBounds}
            onCancelDrawing={cancelDrawingOnly}
          />
        </div>
      )}
      {panelNode}
    </>
  );
};

export default ConstructionAnalysis;
