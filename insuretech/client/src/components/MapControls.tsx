import { useEffect, useMemo, useState } from "react";
import {
  SLOSH_CATEGORIES,
  SLOSH_CATEGORY_LABELS,
  SloshCategory,
  categoryColorWithAlpha
} from "../constants/slosh";
import { COLORS } from "../constants/colors";
import { LAYERS_CONFIG } from "../config/layers";
import { Tooltip } from "react-tooltip";
import { ImageDirection } from "../services/eagleViewDiscovery";

interface MapControlsProps {
  highResEnabled: boolean;
  onHighResToggle: (enabled: boolean) => void;
  floodZoneEnabled: boolean;
  onFloodZoneToggle: (enabled: boolean) => void;
  femaStructuresEnabled: boolean;
  onFemaStructuresToggle: (enabled: boolean) => void;
  sloshEnabled: Partial<Record<SloshCategory, boolean>>;
  onSloshToggle: (category: SloshCategory, enabled: boolean) => void;
  mapTypeId: string;
  onMapTypeChange: (mapTypeId: google.maps.MapTypeId) => void;
  isSatelliteView: boolean;
  isStreetViewActive: boolean;
  overlaysActive: boolean;
  currentZoom: number;
  onRoofAnalysis: () => void;
  onConstructionAnalysis: () => void;
  roofAnalysisActive?: boolean;
  constructionAnalysisActive?: boolean;

  highResLoading?: boolean;
  highResError?: string | null;

  selectedImageDirection: ImageDirection;
  onImageDirectionChange: (direction: ImageDirection) => void;
  availableDirections: ImageDirection[];
}

export default function MapControls({
  highResEnabled,
  onHighResToggle,
  floodZoneEnabled,
  onFloodZoneToggle,
  femaStructuresEnabled,
  onFemaStructuresToggle,
  sloshEnabled,
  onSloshToggle,
  mapTypeId,
  onMapTypeChange,
  isSatelliteView,
  isStreetViewActive,
  overlaysActive,
  currentZoom,
  onRoofAnalysis,
  onConstructionAnalysis,
  roofAnalysisActive = false,
  constructionAnalysisActive = false,

  highResLoading = false,
  highResError = null,

  selectedImageDirection,
  onImageDirectionChange,
  availableDirections
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
    if (highResLoading && !highResEnabled) return "Fetching authentication token…";
    if (highResLoading) return "Loading EagleView imagery…";
    if (highResError) return highResError;
    return "";
  }, [highResError, highResLoading, highResEnabled]);

  const handleToggle = () => {
    if (isDisabled) return;
    onHighResToggle(!highResEnabled);
  };

  const handleFloodToggle = () => {
    onFloodZoneToggle(!floodZoneEnabled);
  };

  const handleFemaStructuresToggle = () => {
    onFemaStructuresToggle(!femaStructuresEnabled);
  };

  const MIN_ZOOM_FOR_ROOF_ANALYSIS = 21;

  const overlaysDisabledMessage = useMemo(() => (
    overlaysActive ? "Disable overlays to run analyses." : ""
  ), [overlaysActive]);

  const constructionDisabled = overlaysActive || !isStreetViewActive;
  const roofDisabled = overlaysActive || !isSatelliteView || currentZoom < MIN_ZOOM_FOR_ROOF_ANALYSIS;

  const constructionTitle = overlaysDisabledMessage || (isStreetViewActive ? undefined : "Switch to Street View to enable construction analysis.");
  const roofTitle = useMemo(() => {
    if (overlaysDisabledMessage) return overlaysDisabledMessage;
    if (!isSatelliteView) return "Switch to Satellite view to enable roof analysis.";
    if (currentZoom < MIN_ZOOM_FOR_ROOF_ANALYSIS) return `Zoom in to level ${MIN_ZOOM_FOR_ROOF_ANALYSIS} or higher to enable roof analysis. Current zoom: ${Math.round(currentZoom)}`;
    return undefined;
  }, [overlaysDisabledMessage, isSatelliteView, currentZoom]);

  const constructionButtonClasses = `${"w-full rounded-md px-3 py-2 text-sm font-medium transition-colors"} ${
    constructionAnalysisActive ? "bg-blue-600 text-white shadow" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
  } ${constructionDisabled ? "cursor-not-allowed opacity-60 hover:bg-gray-100" : ""}`;

  const roofButtonClasses = `${"w-full rounded-md px-3 py-2 text-sm font-medium transition-colors"} ${
    roofAnalysisActive ? "bg-blue-600 text-white shadow" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
  } ${roofDisabled ? "cursor-not-allowed opacity-60 hover:bg-gray-100" : ""}`;

  return (
    <div className="absolute top-4 right-4 z-30">
      <div className={`${COLORS.panelBackground} ${COLORS.panelRounded} ${COLORS.panelShadow} border ${COLORS.panelBorder} w-64`}>
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
            {LAYERS_CONFIG.highres && (
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
                {highResEnabled && availableDirections.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-xs font-medium text-gray-600 mb-2">View Direction</p>
                    <div className="flex gap-1">
                      {[
                        { value: "ortho" as const, label: "V", title: "Vertical (Ortho)" },
                        { value: "north" as const, label: "N", title: "North Oblique" },
                        { value: "east" as const, label: "E", title: "East Oblique" },
                        { value: "south" as const, label: "S", title: "South Oblique" },
                        { value: "west" as const, label: "W", title: "West Oblique" }
                      ].map(({ value, label, title }) => {
                        const isAvailable = availableDirections.includes(value);
                        const isActive = selectedImageDirection === value;
                        return (
                          <button
                            key={value}
                            type="button"
                            onClick={() => isAvailable && onImageDirectionChange(value)}
                            disabled={!isAvailable}
                            title={title}
                            className={`flex-1 rounded px-2 py-1.5 text-xs font-medium transition-colors ${
                              isActive
                                ? "bg-blue-600 text-white shadow"
                                : isAvailable
                                ? "bg-gray-100 text-gray-700 hover:bg-gray-200"
                                : "bg-gray-50 text-gray-400 cursor-not-allowed"
                            }`}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
            {LAYERS_CONFIG.floodzone && (
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
            )}

            {LAYERS_CONFIG.fema && (
              <div className="px-4 py-3 border-t border-gray-200">
                <div className="flex items-center justify-between">
                  <label htmlFor="fema-structures-toggle" className="text-sm font-medium text-gray-700">
                    FEMA Structures
                  </label>
                  <button
                    id="fema-structures-toggle"
                    type="button"
                    onClick={handleFemaStructuresToggle}
                    aria-pressed={femaStructuresEnabled}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                      femaStructuresEnabled ? "bg-blue-600" : "bg-gray-300"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                        femaStructuresEnabled ? "translate-x-6" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              </div>
            )}

            {LAYERS_CONFIG.slosh && (
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
            )}

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
                  data-tooltip-id="construction-analysis-tooltip"
                  data-tooltip-content={constructionTitle || "Construction Analysis requires Google Street View"}
                >
                  {constructionAnalysisActive ? "Construction Analysis Active" : "Run Construction Analysis"}
                </button>
                <Tooltip id="construction-analysis-tooltip" place="left" style={{ zIndex: 9999 }} />

                <button
                  type="button"
                  onClick={() => {
                    if (roofDisabled) return;
                    onRoofAnalysis();
                  }}
                  disabled={roofDisabled}
                  className={roofButtonClasses}
                  data-tooltip-id="roof-analysis-tooltip"
                  data-tooltip-content={roofTitle || `Roof Analysis requires Satellite view and zoom level ${MIN_ZOOM_FOR_ROOF_ANALYSIS}+`}
                >
                  {roofAnalysisActive ? "Roof Analysis Active" : "Run Roof Analysis"}
                </button>
                <Tooltip id="roof-analysis-tooltip" place="left" style={{ zIndex: 9999 }} />
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
