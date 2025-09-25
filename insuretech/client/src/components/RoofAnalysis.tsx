import React, { useCallback, useMemo, useState } from "react";
import html2canvas from "html2canvas";
import DrawingCanvas from "./DrawingCanvas";

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
}

const DEFAULT_API_URL =
  "https://mathandpencil--roof-analysis-api-fastapi-app.modal.run/save-image";

const RoofAnalysis: React.FC<RoofAnalysisProps> = ({
  active,
  mapContainerRef,
  onExit
}) => {
  const [selectedBounds, setSelectedBounds] = useState<Bounds | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [responseData, setResponseData] = useState<unknown | null>(null);

  const apiUrl = useMemo(
    () => import.meta.env.VITE_ROOF_ANALYSIS_API_URL || DEFAULT_API_URL,
    []
  );

  const apiToken = import.meta.env.VITE_ACORD_API_TOKEN;

  const resetState = useCallback(() => {
    setSelectedBounds(null);
    setErrorMessage(null);
    setResponseData(null);
  }, []);

  const handleDrawComplete = useCallback(
    async (bounds: Bounds) => {
      if (!mapContainerRef.current) {
        setErrorMessage("Map view is not ready for capture.");
        return;
      }

      if (!apiToken) {
        setErrorMessage("Missing roof analysis API token (VITE_API_TOKEN).");
        return;
      }

      const mapElement = mapContainerRef.current.querySelector(
        ".gm-style"
      ) as HTMLElement | null;
      if (!mapElement) {
        setErrorMessage("Unable to locate the Google Maps canvas for capture.");
        return;
      }

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
      const clampStartY = Math.min(
        Math.max(0, captureBounds.y),
        mapRect.height
      );
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
        setErrorMessage(
          "Selection must stay within the map view. Please try again."
        );
        return;
      }

      setSelectedBounds(bounds);
      setIsUploading(true);
      setErrorMessage(null);
      setResponseData(null);

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

        const response = await fetch(apiUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${apiToken}`
          },
          body: JSON.stringify({ image_data: imageData })
        });

        if (!response.ok) {
          throw new Error(`Roof analysis request failed (${response.status})`);
        }

        const payload = await response.json();
        setResponseData(payload);
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Unknown error while processing roof analysis.";
        setErrorMessage(message);
      } finally {
        setIsUploading(false);
      }
    },
    [apiToken, apiUrl, mapContainerRef]
  );

  if (!active) {
    return null;
  }

  return (
    <div className="absolute inset-0 z-30 flex flex-col" aria-live="polite">
      <DrawingCanvas
        onDrawComplete={handleDrawComplete}
        disabled={isUploading}
        highlight={selectedBounds}
      />
      <div className="pointer-events-none absolute left-1/2 top-4 z-40 w-full max-w-md -translate-x-1/2 px-4">
        <div className="pointer-events-auto rounded-md border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-slate-900">
                Roof analysis mode
              </h3>
              <p className="mt-1 text-sm text-slate-600">
                Click and drag on the map to draw a bounding box around the
                roof. The selected area will be uploaded for analysis.
              </p>
            </div>
            <button
              type="button"
              className="rounded border border-slate-200 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
              onClick={() => {
                resetState();
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
          {isUploading && (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
              Uploading selection to roof analysis service…
            </div>
          )}
          {errorMessage && (
            <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {errorMessage}
            </div>
          )}
          {responseData !== null && (
            <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2">
              <div className="text-sm font-medium text-emerald-800">
                Roof analysis response
              </div>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs text-emerald-900">
                {JSON.stringify(responseData, null, 2)}
              </pre>
            </div>
          )}
          {selectedBounds && !isUploading && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="rounded border border-slate-200 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50"
                onClick={() => resetState()}
              >
                Draw again
              </button>
              <button
                type="button"
                className="rounded border border-slate-200 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50"
                onClick={() => {
                  resetState();
                  onExit();
                }}
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RoofAnalysis;
