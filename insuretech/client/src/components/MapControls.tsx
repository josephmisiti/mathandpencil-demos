import { useEffect, useMemo, useState } from "react";
import {
  SLOSH_CATEGORIES,
  SLOSH_CATEGORY_LABELS,
  SloshCategory,
  categoryColorWithAlpha
} from "../constants/slosh";

interface MapControlsProps {
  highResEnabled: boolean;
  onHighResToggle: (enabled: boolean) => void;
  floodZoneEnabled: boolean;
  onFloodZoneToggle: (enabled: boolean) => void;
  sloshEnabled: Partial<Record<SloshCategory, boolean>>;
  onSloshToggle: (category: SloshCategory, enabled: boolean) => void;
  mapTypeId: string;
  onMapTypeChange: (mapTypeId: google.maps.MapTypeId) => void;
  isSatelliteView: boolean;
  overlaysActive: boolean;
  onRoofAnalysis: () => void;
  onConstructionAnalysis: () => void;
  roofAnalysisActive?: boolean;
  constructionAnalysisActive?: boolean;

  highResLoading?: boolean;
  highResError?: string | null;
}

export default function MapControls({
  highResEnabled,
  onHighResToggle,
  floodZoneEnabled,
  onFloodZoneToggle,
  sloshEnabled,
  onSloshToggle,
  mapTypeId,
  onMapTypeChange,
  isSatelliteView,
  overlaysActive,
  onRoofAnalysis,
  onConstructionAnalysis,
  roofAnalysisActive = false,
  constructionAnalysisActive = false,

  highResLoading = false,
  highResError = null
}: MapControlsProps) {
  const STORAGE_KEY = "map-controls-open";
  const [isOpen, setIsOpen] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(STORAGE_KEY) === "true";
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(STORAGE_KEY, String(isOpen));
  }, [isOpen]);

  const isDisabled = highResLoading;

  const statusMessage = useMemo(() => {
    if (highResLoading) return "Loading EagleView imagery…";
    if (highResError) return highResError;
    return "";
  }, [highResError, highResLoading]);

  const handleToggle = () => {
    if (isDisabled) return;
    onHighResToggle(!highResEnabled);
  };

  const handleFloodToggle = () => {
    onFloodZoneToggle(!floodZoneEnabled);
  };

  const overlaysDisabledMessage = useMemo(() => (
    overlaysActive ? "Disable overlays to run analyses." : ""
  ), [overlaysActive]);

  const constructionDisabled = overlaysActive;
  const roofDisabled = overlaysActive || !isSatelliteView;

  const constructionTitle = overlaysDisabledMessage || undefined;
  const roofTitle = overlaysDisabledMessage || (isSatelliteView ? undefined : "Switch to Satellite view to enable roof analysis.");

  const constructionButtonClasses = `${"w-full rounded-md px-3 py-2 text-sm font-medium transition-colors"} ${
    constructionAnalysisActive ? "bg-blue-600 text-white shadow" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
  } ${constructionDisabled ? "cursor-not-allowed opacity-60 hover:bg-gray-100" : ""}`;

  const roofButtonClasses = `${"w-full rounded-md px-3 py-2 text-sm font-medium transition-colors"} ${
    roofAnalysisActive ? "bg-blue-600 text-white shadow" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
  } ${roofDisabled ? "cursor-not-allowed opacity-60 hover:bg-gray-100" : ""}`;

  return (
    <div className="absolute top-4 right-4 z-20">
      <div className="bg-white rounded-lg shadow-lg border border-gray-200 min-w-64">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full px-4 py-3 text-left font-medium text-gray-700 hover:bg-gray-50 rounded-t-lg flex items-center justify-between"
        >
          <span>Map Controls</span>
          <svg
            className={`w-4 h-4 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {isOpen && (
          <div className="border-t border-gray-200">
            <div className="px-4 py-3 border-b border-gray-200">
              <p className="text-sm font-medium text-gray-700">Basemap</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {[
                  { label: "Map", value: "roadmap" as const },
                  { label: "Satellite", value: "satellite" as const }
                ].map(({ label, value }) => {
                  const isActive = mapTypeId === value || (value === "satellite" && isSatelliteView);
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => onMapTypeChange(value)}
                      className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-blue-600 text-white shadow"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="px-4 py-3">
              <div className="flex items-center justify-between">
                <label htmlFor="high-res-toggle" className="text-sm font-medium text-gray-700">
                  High Res Imagery
                </label>
                <button
                  id="high-res-toggle"
                  type="button"
                  onClick={handleToggle}
                  disabled={isDisabled}
                  aria-pressed={highResEnabled}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                    highResEnabled ? "bg-blue-600" : "bg-gray-300"
                  } ${isDisabled ? "opacity-60 cursor-not-allowed" : ""}`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                      highResEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
              {statusMessage && (
                <p className="mt-2 text-xs text-gray-500">
                  {statusMessage}
                </p>
              )}
            </div>
            <div className="px-4 py-3 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <label htmlFor="flood-zone-toggle" className="text-sm font-medium text-gray-700">
                  Flood Zone Overlay
                </label>
                <button
                  id="flood-zone-toggle"
                  type="button"
                  onClick={handleFloodToggle}
                  aria-pressed={floodZoneEnabled}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                    floodZoneEnabled ? "bg-blue-600" : "bg-gray-300"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                      floodZoneEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
            </div>

            <div className="px-4 py-3 border-t border-gray-200 space-y-2">
              <p className="text-sm font-medium text-gray-700">SLOSH Inundation</p>
              <div className="space-y-2">
                {SLOSH_CATEGORIES.map((category) => {
                  const enabled = sloshEnabled[category] ?? false;
                  const swatchColor = categoryColorWithAlpha(category);
                  return (
                    <div key={category} className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-xs text-gray-600">
                        <span
                          className="inline-block h-2.5 w-4 rounded-sm border border-gray-200"
                          style={{ backgroundColor: swatchColor }}
                        />
                        <span>{SLOSH_CATEGORY_LABELS[category]}</span>
                      </span>
                      <button
                        type="button"
                        onClick={() => onSloshToggle(category, !enabled)}
                        aria-pressed={enabled}
                        className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                          enabled ? "bg-blue-600" : "bg-gray-300"
                        }`}
                      >
                        <span
                          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform duration-200 ${
                            enabled ? "translate-x-5" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="px-4 py-3 border-t border-gray-200 space-y-2">
              <p className="text-sm font-medium text-gray-700">Analysis Tools</p>
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => {
                    if (constructionDisabled) return;
                    onConstructionAnalysis();
                  }}
                  disabled={constructionDisabled}
                  className={constructionButtonClasses}
                  title={constructionTitle}
                >
                  {constructionAnalysisActive ? "Construction Analysis Active" : "Run Construction Analysis"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (roofDisabled) return;
                    onRoofAnalysis();
                  }}
                  disabled={roofDisabled}
                  className={roofButtonClasses}
                  title={roofTitle}
                >
                  {roofAnalysisActive ? "Roof Analysis Active" : "Run Roof Analysis"}
                </button>
              </div>
              {overlaysDisabledMessage && (
                <p className="text-xs text-gray-500">{overlaysDisabledMessage}</p>
              )}
              {!overlaysDisabledMessage && !isSatelliteView && (
                <p className="text-xs text-gray-500">Switch to Satellite view to enable roof analysis.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
