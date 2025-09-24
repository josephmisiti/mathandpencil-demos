import { useEffect, useMemo, useRef, useState } from "react";
import { Map, Marker, InfoWindow, useMap } from "@vis.gl/react-google-maps";
import { MapProps, Location } from "../types/location";
import MarkerInfo from "./MarkerInfo";
import MapControls from "./MapControls";
import { useEagleViewImagery } from "../hooks/useEagleViewImagery";
import EagleViewOverlay from "./EagleViewOverlay";
import FloodZoneOverlay from "./FloodZoneOverlay";
import SloshOverlay from "./SloshOverlay";
import FloodZoneLegend from "./FloodZoneLegend";
import SloshLegend from "./SloshLegend";
import MeasurementPolygon from "./MeasurementPolygon";
import DistanceMeasurement from "./DistanceMeasurement";
import { SLOSH_CATEGORIES, SloshCategory } from "../constants/slosh";

export default function MapView({
  center,
  markers,
  zoom = 12,
  onViewChange
}: MapProps) {
  const [selectedMarker, setSelectedMarker] = useState<Location | null>(null);
  const [highResEnabled, setHighResEnabled] = useState(false);
  const [floodZoneEnabled, setFloodZoneEnabled] = useState(false);
  const [sloshEnabled, setSloshEnabled] = useState<Record<SloshCategory, boolean>>(
    () => {
      const initial = {} as Record<SloshCategory, boolean>;
      SLOSH_CATEGORIES.forEach((category) => {
        initial[category] = false;
      });
      return initial;
    }
  );
  const [highResErrorMessage, setHighResErrorMessage] = useState<string | null>(
    null
  );
  const [mapZoom, setMapZoom] = useState(zoom);
  const [mapCenter, setMapCenter] = useState<google.maps.LatLngLiteral>({
    lat: center.lat,
    lng: center.lng
  });
  const mapCenterRef = useRef(mapCenter);
  const mapZoomRef = useRef(mapZoom);
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const [contextMenu, setContextMenu] = useState<
    | null
    | {
        latLng: google.maps.LatLngLiteral;
        position: { x: number; y: number };
      }
  >(null);
  const [measureMode, setMeasureMode] = useState(false);
  const [polygonPoints, setPolygonPoints] = useState<google.maps.LatLngLiteral[]>([]);
  const [polygonArea, setPolygonArea] = useState<number | null>(null);
  const [distanceMode, setDistanceMode] = useState(false);
  const [distancePoints, setDistancePoints] = useState<google.maps.LatLngLiteral[]>([]);
  const [distance, setDistance] = useState<number | null>(null);

  const { imagery, status, error } = useEagleViewImagery(
    highResEnabled,
    center
  );

  const overlayImagery = useMemo(() => {
    if (!highResEnabled || status !== "ready") return null;
    return imagery;
  }, [highResEnabled, imagery, status]);

  // Calculate polygon area using the shoelace formula
  const calculatePolygonArea = (points: google.maps.LatLngLiteral[]): number => {
    if (points.length < 3) return 0;

    // Convert degrees to meters using approximate conversion
    // This is a simplified calculation - for precise measurements, you'd use geodesic calculations
    const earthRadius = 6371000; // meters
    const degToRad = Math.PI / 180;

    // Calculate area using shoelace formula with spherical approximation
    let area = 0;
    for (let i = 0; i < points.length; i++) {
      const j = (i + 1) % points.length;
      const xi = points[i].lng * degToRad * earthRadius * Math.cos(points[i].lat * degToRad);
      const yi = points[i].lat * degToRad * earthRadius;
      const xj = points[j].lng * degToRad * earthRadius * Math.cos(points[j].lat * degToRad);
      const yj = points[j].lat * degToRad * earthRadius;
      area += xi * yj - xj * yi;
    }
    return Math.abs(area) / 2;
  };

  // Check if a point is close to the first point (for auto-snap)
  const isCloseToStart = (point: google.maps.LatLngLiteral, threshold: number = 0.0001): boolean => {
    if (polygonPoints.length < 3) return false;
    const startPoint = polygonPoints[0];
    const distance = Math.sqrt(
      Math.pow(point.lat - startPoint.lat, 2) + Math.pow(point.lng - startPoint.lng, 2)
    );
    return distance < threshold;
  };

  // Calculate distance between two points using the Haversine formula
  const calculateDistance = (point1: google.maps.LatLngLiteral, point2: google.maps.LatLngLiteral): number => {
    const earthRadius = 6371000; // meters
    const degToRad = Math.PI / 180;

    const lat1Rad = point1.lat * degToRad;
    const lat2Rad = point2.lat * degToRad;
    const deltaLatRad = (point2.lat - point1.lat) * degToRad;
    const deltaLngRad = (point2.lng - point1.lng) * degToRad;

    const a = Math.sin(deltaLatRad / 2) * Math.sin(deltaLatRad / 2) +
              Math.cos(lat1Rad) * Math.cos(lat2Rad) *
              Math.sin(deltaLngRad / 2) * Math.sin(deltaLngRad / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return earthRadius * c; // distance in meters
  };

  const handleHighResToggle = (enabled: boolean) => {
    setHighResEnabled(enabled);
    if (enabled) {
      setHighResErrorMessage(null);
    }
  };

  useEffect(() => {
    setMapZoom(zoom);
    mapZoomRef.current = zoom;
  }, [zoom]);

  useEffect(() => {
    const nextCenter = { lat: center.lat, lng: center.lng };
    setMapCenter(nextCenter);
    mapCenterRef.current = nextCenter;
  }, [center.lat, center.lng]);

  useEffect(() => {
    mapCenterRef.current = mapCenter;
  }, [mapCenter]);

  useEffect(() => {
    mapZoomRef.current = mapZoom;
  }, [mapZoom]);

  useEffect(() => {
    if (status === "ready") {
      setHighResErrorMessage(null);
    }
  }, [status]);

  useEffect(() => {
    if (!highResEnabled) return;

    if (status === "error") {
      setHighResEnabled(false);
      const message = error || "Failed to load EagleView imagery.";
      setHighResErrorMessage(message);
      console.error("EagleView imagery error:", message);
    }
  }, [error, highResEnabled, status]);

  useEffect(() => {
    if (!floodZoneEnabled) {
      setContextMenu(null);
    }
  }, [floodZoneEnabled]);

  // Combined ESC key handler for both context menu and measurement mode
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        console.log("ESC pressed", { measureMode, contextMenu: !!contextMenu });

        if (measureMode) {
          console.log("Canceling measurement mode");
          event.preventDefault();
          event.stopPropagation();
          setMeasureMode(false);
          setPolygonPoints([]);
          setPolygonArea(null);
        }

        if (distanceMode) {
          console.log("Canceling distance mode");
          event.preventDefault();
          event.stopPropagation();
          setDistanceMode(false);
          setDistancePoints([]);
          setDistance(null);
        }

        if (contextMenu) {
          console.log("Closing context menu");
          setContextMenu(null);
        }
      }
    };

    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
    };
  }, [measureMode, distanceMode, contextMenu]);

  // Cleanup when measurement mode is disabled
  useEffect(() => {
    if (!measureMode) {
      console.log("Measurement mode disabled - clearing polygon data");
      setPolygonPoints([]);
      setPolygonArea(null);
    }
  }, [measureMode]);

  // Only cleanup distance data when explicitly requested via ESC or Clear button
  // Don't auto-clear when distanceMode becomes false, as we want to show the result

  return (
    <div ref={mapContainerRef} className="relative h-screen w-screen">
      <MapControls
        highResEnabled={highResEnabled}
        onHighResToggle={handleHighResToggle}
        floodZoneEnabled={floodZoneEnabled}
        onFloodZoneToggle={setFloodZoneEnabled}
        sloshEnabled={sloshEnabled}
        onSloshToggle={(category, enabled) =>
          setSloshEnabled((prev) => ({ ...prev, [category]: enabled }))
        }
        highResLoading={status === "loading"}
        highResError={highResErrorMessage}
      />
      <Map
        zoom={mapZoom}
        center={mapCenter}
        gestureHandling={"auto"}
        disableDefaultUI={true}
        zoomControl={true}
        zoomControlOptions={{
          position: google.maps.ControlPosition.LEFT_CENTER
        }}
        streetViewControl={true}
        streetViewControlOptions={{
          position: google.maps.ControlPosition.LEFT_CENTER
        }}
        mapTypeControl={true}
        mapTypeControlOptions={{
          position: google.maps.ControlPosition.LEFT_BOTTOM
        }}
        fullscreenControl={false}
        onZoomChanged={(event) => {
          const newZoom = event.detail.zoom;
          setMapZoom(newZoom);
          mapZoomRef.current = newZoom;
          onViewChange?.({ center: mapCenterRef.current, zoom: newZoom });
        }}
        onCenterChanged={(event) => {
          const newCenter = event.detail.center;
          setMapCenter(newCenter);
          mapCenterRef.current = newCenter;
          onViewChange?.({ center: newCenter, zoom: mapZoomRef.current });
        }}
        onClick={(event) => {
          setContextMenu(null);

          // Handle polygon drawing
          if (measureMode) {
            const clickedLatLng = event.detail.latLng;
            if (!clickedLatLng) return;

            // Check if we should auto-snap to close the polygon
            if (isCloseToStart(clickedLatLng)) {
              // Close the polygon
              const area = calculatePolygonArea(polygonPoints);
              setPolygonArea(area);
              setMeasureMode(false);
              console.log(`Polygon area: ${area.toLocaleString()} square meters`);
              console.log(`Polygon area: ${(area * 0.000247105).toFixed(2)} acres`);
              return;
            }

            // Add point to polygon
            setPolygonPoints(prev => [...prev, clickedLatLng]);
          }

          // Handle distance measurement
          if (distanceMode) {
            const clickedLatLng = event.detail.latLng;
            if (!clickedLatLng) return;

            if (distancePoints.length === 0) {
              // First point
              setDistancePoints([clickedLatLng]);
            } else if (distancePoints.length === 1) {
              // Second point - calculate distance
              const newPoints = [...distancePoints, clickedLatLng];
              setDistancePoints(newPoints);

              const dist = calculateDistance(distancePoints[0], clickedLatLng);
              setDistance(dist);
              setDistanceMode(false);

              console.log(`Distance: ${dist.toFixed(2)} meters`);
              console.log(`Distance: ${(dist * 3.28084).toFixed(2)} feet`);
            }
          }
        }}
        onContextmenu={(event) => {
          // Show context menu if flood zone is enabled OR no layers are enabled
          const noLayersEnabled = !floodZoneEnabled && !SLOSH_CATEGORIES.some(category => sloshEnabled[category]);
          if (!floodZoneEnabled && !noLayersEnabled) return;

          const clickedLatLng = event.detail.latLng;
          if (!clickedLatLng) return;

          const domEvent = event.domEvent as MouseEvent | undefined;
          if (domEvent) {
            domEvent.preventDefault();
            domEvent.stopPropagation();
          }

          const containerRect = mapContainerRef.current?.getBoundingClientRect();
          const MENU_WIDTH = 180;
          const MENU_HEIGHT = 60;

          let position = { x: 0, y: 0 };
          if (domEvent && containerRect) {
            const rawX = domEvent.clientX - containerRect.left;
            const rawY = domEvent.clientY - containerRect.top;
            position = {
              x: Math.max(
                0,
                Math.min(rawX, Math.max(containerRect.width - MENU_WIDTH, 0))
              ),
              y: Math.max(
                0,
                Math.min(rawY, Math.max(containerRect.height - MENU_HEIGHT, 0))
              )
            };
          } else if (containerRect) {
            position = {
              x: Math.max(containerRect.width / 2 - MENU_WIDTH / 2, 0),
              y: Math.max(containerRect.height / 2 - MENU_HEIGHT / 2, 0)
            };
          }

          setContextMenu({ latLng: clickedLatLng, position });
        }}
      >
        <EagleViewOverlay enabled={!!overlayImagery} imagery={overlayImagery} />
        <FloodZoneOverlay enabled={floodZoneEnabled} />
        <SloshOverlay
          enabledCategories={SLOSH_CATEGORIES.filter((category) => sloshEnabled[category])}
        />

        {/* Render measurement polygon using custom component */}
        <MeasurementPolygon points={polygonPoints} area={polygonArea} />

        {/* Render distance measurement using custom component */}
        <DistanceMeasurement
          points={distancePoints}
          distance={distance}
          onClear={() => {
            setDistance(null);
            setDistancePoints([]);
          }}
        />

        {markers.map((marker) => (
          <Marker
            key={`${marker.lat}-${marker.lng}`}
            position={marker}
            onClick={() => setSelectedMarker(marker)}
          />
        ))}

        {selectedMarker && (
          <InfoWindow
            position={selectedMarker}
            onCloseClick={() => setSelectedMarker(null)}
          >
            <MarkerInfo
              location={selectedMarker}
              onClose={() => setSelectedMarker(null)}
            />
          </InfoWindow>
        )}
      </Map>
      {(() => {
        const sloshVisible = SLOSH_CATEGORIES.some((category) => sloshEnabled[category]);
        const showAnyLegend = floodZoneEnabled || sloshVisible;

        if (!showAnyLegend) {
          return null;
        }

        return (
          <div className="absolute bottom-4 right-4 z-20 flex flex-col items-end gap-3">
            {sloshVisible && (
              <SloshLegend
                enabledCategories={sloshEnabled}
                className="relative"
              />
            )}
            {floodZoneEnabled && <FloodZoneLegend className="relative" />}
          </div>
        );
      })()}

      {/* Area measurement result display */}
      {polygonArea !== null && distance === null && (
        <div className="absolute top-4 right-4 z-20 rounded-md border border-slate-200 bg-white p-3 shadow-lg">
          <div className="text-sm font-medium text-slate-700">Area Measurement</div>
          <div className="text-lg font-bold text-slate-900">
            {polygonArea.toLocaleString()} m²
          </div>
          <div className="text-sm text-slate-600">
            {(polygonArea * 0.000247105).toFixed(2)} acres
          </div>
          <button
            onClick={() => {
              setPolygonArea(null);
              setPolygonPoints([]);
            }}
            className="mt-2 text-xs text-slate-500 hover:text-slate-700"
          >
            Clear
          </button>
        </div>
      )}


      {/* Measurement instructions */}
      {measureMode && (
        <div className="absolute top-4 left-1/2 z-20 -translate-x-1/2 rounded-md border border-slate-200 bg-white p-3 shadow-lg">
          <div className="text-sm text-slate-700">
            {polygonPoints.length === 0 && "Click on the map to start drawing a polygon"}
            {polygonPoints.length === 1 && "Continue clicking to add points"}
            {polygonPoints.length === 2 && "Add at least one more point to create a polygon"}
            {polygonPoints.length >= 3 && (
              <div>
                Click near the first point to close the polygon
                <br />
                <span className="text-xs text-slate-500">
                  Right-click for options
                </span>
              </div>
            )}
            <div className="text-xs text-slate-500 mt-1 border-t pt-1">
              Press ESC to cancel
            </div>
          </div>
        </div>
      )}

      {/* Distance measurement instructions */}
      {distanceMode && (
        <div className="absolute top-4 left-1/2 z-20 -translate-x-1/2 rounded-md border border-slate-200 bg-white p-3 shadow-lg">
          <div className="text-sm text-slate-700">
            {distancePoints.length === 0 && "Click on the map to select the first point"}
            {distancePoints.length === 1 && "Click on the map to select the second point"}
            <div className="text-xs text-slate-500 mt-1 border-t pt-1">
              Press ESC to cancel
            </div>
          </div>
        </div>
      )}

      {contextMenu && (
        <div
          className="absolute z-30 min-w-[180px] rounded-md border border-slate-200 bg-white py-1 shadow-lg"
          style={{ left: contextMenu.position.x, top: contextMenu.position.y }}
          onClick={(event) => event.stopPropagation()}
        >
          {floodZoneEnabled && (
            <button
              className="block w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
              onClick={() => {
                const url = new URL("http://localhost:3005/api/v1/floodzone");
                url.searchParams.set("lat", contextMenu.latLng.lat.toString());
                url.searchParams.set("lng", contextMenu.latLng.lng.toString());
                window.open(url.toString(), "_blank", "noopener,noreferrer");
                setContextMenu(null);
              }}
            >
              Go to Floodzone API
            </button>
          )}

          {/* Show Measure area option when no layers are enabled */}
          {!floodZoneEnabled && !SLOSH_CATEGORIES.some(category => sloshEnabled[category]) && (
            <>
              {!measureMode && !distanceMode && (
                <>
                  <button
                    className="block w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
                    onClick={() => {
                      setMeasureMode(true);
                      setPolygonPoints([]);
                      setPolygonArea(null);
                      setContextMenu(null);
                    }}
                  >
                    📐 Measure area
                  </button>
                  <button
                    className="block w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
                    onClick={() => {
                      setDistanceMode(true);
                      setDistancePoints([]);
                      setDistance(null);
                      setContextMenu(null);
                    }}
                  >
                    📏 Measure distance
                  </button>
                </>
              )}

              {measureMode && (
                <>
                  <button
                    className="block w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
                    onClick={() => {
                      setMeasureMode(false);
                      setPolygonPoints([]);
                      setPolygonArea(null);
                      setContextMenu(null);
                    }}
                  >
                    ❌ Cancel area measurement
                  </button>

                  {polygonPoints.length >= 3 && (
                    <button
                      className="block w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
                      onClick={() => {
                        const area = calculatePolygonArea(polygonPoints);
                        setPolygonArea(area);
                        setMeasureMode(false);
                        setContextMenu(null);
                        console.log(`Polygon area: ${area.toLocaleString()} square meters`);
                        console.log(`Polygon area: ${(area * 0.000247105).toFixed(2)} acres`);
                      }}
                    >
                      ✅ Finish area measurement
                    </button>
                  )}
                </>
              )}

              {distanceMode && (
                <button
                  className="block w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
                  onClick={() => {
                    setDistanceMode(false);
                    setDistancePoints([]);
                    setDistance(null);
                    setContextMenu(null);
                  }}
                >
                  ❌ Cancel distance measurement
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
