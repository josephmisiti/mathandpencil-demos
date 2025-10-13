import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map, Marker, InfoWindow } from "@vis.gl/react-google-maps";
// import { DeckGLOverlay } from "@deck.gl/google-maps";
import { MapProps, Location } from "../types/location";
import MarkerInfo from "./MarkerInfo";
import MapControls from "./MapControls";
import { useEagleViewImagery } from "../hooks/useEagleViewImagery";
import { EagleViewOverlay } from "./EagleViewOverlay";
import FloodZoneOverlay from "./FloodZoneOverlay";
import SloshOverlay from "./SloshOverlay";
import FemaStructuresOverlay from "./FemaStructuresOverlay";
import FloodZoneLegend from "./FloodZoneLegend";
import SloshLegend from "./SloshLegend";
import MeasurementPolygon from "./MeasurementPolygon";
import DistanceMeasurement from "./DistanceMeasurement";
import RoofAnalysis from "./RoofAnalysis";
import ConstructionAnalysis from "./ConstructionAnalysis";
import { SLOSH_CATEGORIES, SloshCategory } from "../constants/slosh";

export default function MapView({
  center,
  markers,
  zoom = 12,
  onViewChange,
  onRoofAnalysisVisibilityChange,
  roofAnalysisPanelRef,
  onConstructionAnalysisVisibilityChange,
  constructionAnalysisPanelRef
}: MapProps) {
  const [selectedMarker, setSelectedMarker] = useState<Location | null>(null);
  const [highResEnabled, setHighResEnabled] = useState(false);
  const [floodZoneEnabled, setFloodZoneEnabled] = useState(false);
  const [femaStructuresEnabled, setFemaStructuresEnabled] = useState(false);
  const [sloshEnabled, setSloshEnabled] = useState<
    Record<SloshCategory, boolean>
  >(() => {
    const initial = {} as Record<SloshCategory, boolean>;
    SLOSH_CATEGORIES.forEach((category) => {
      initial[category] = false;
    });
    return initial;
  });
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
  const mapInstanceRef = useRef<google.maps.Map | null>(null);
  const streetViewRef = useRef<google.maps.StreetViewPanorama | null>(null);
  const [contextMenu, setContextMenu] = useState<null | {
    latLng: google.maps.LatLngLiteral;
    position: { x: number; y: number };
  }>(null);
  const [measureMode, setMeasureMode] = useState(false);
  const [polygonPoints, setPolygonPoints] = useState<
    google.maps.LatLngLiteral[]
  >([]);
  const [polygonArea, setPolygonArea] = useState<number | null>(null);
  const [distanceMode, setDistanceMode] = useState(false);
  const [distancePoints, setDistancePoints] = useState<
    google.maps.LatLngLiteral[]
  >([]);
  const [distance, setDistance] = useState<number | null>(null);
  const [roofAnalysisVisible, setRoofAnalysisVisible] = useState(false);
  const [roofAnalysisOverlay, setRoofAnalysisOverlay] = useState(false);
  const [constructionAnalysisVisible, setConstructionAnalysisVisible] =
    useState(false);
  const [constructionAnalysisOverlay, setConstructionAnalysisOverlay] =
    useState(false);
  const [mapTypeId, setMapTypeId] = useState<string>("roadmap");
  const [streetViewVisible, setStreetViewVisible] = useState(false);
  const streetViewListenerRef = useRef<google.maps.MapsEventListener | null>(
    null
  );

  const isSatelliteView = mapTypeId === "satellite" || mapTypeId === "hybrid";

  const updateRoofAnalysisVisibility = useCallback(
    (visible: boolean) => {
      setRoofAnalysisVisible(visible);
      onRoofAnalysisVisibilityChange?.(visible);
    },
    [onRoofAnalysisVisibilityChange]
  );

  const updateConstructionAnalysisVisibility = useCallback(
    (visible: boolean) => {
      setConstructionAnalysisVisible(visible);
      onConstructionAnalysisVisibilityChange?.(visible);
    },
    [onConstructionAnalysisVisibilityChange]
  );

  const sloshActive = useMemo(
    () => SLOSH_CATEGORIES.some((category) => sloshEnabled[category]),
    [sloshEnabled]
  );
  const overlaysActive = floodZoneEnabled || sloshActive || femaStructuresEnabled;

  const exitStreetView = useCallback(() => {
    const streetView = streetViewRef.current;
    if (streetView?.getVisible?.()) {
      streetView.setVisible(false);
    }
  }, []);

  const ensureSatelliteView = useCallback(() => {
    const map = mapInstanceRef.current;
    if (!map) {
      return;
    }

    const currentType = map.getMapTypeId?.();
    const isAlreadySatellite =
      currentType === "satellite" || currentType === "hybrid";
    if (isAlreadySatellite) {
      return;
    }

    map.setMapTypeId?.("satellite");
    setMapTypeId("satellite");
  }, [setMapTypeId]);

  const openRoofAnalysis = useCallback(() => {
    if (!isSatelliteView || overlaysActive) {
      return;
    }
    exitStreetView();
    ensureSatelliteView();
    updateRoofAnalysisVisibility(true);
    setRoofAnalysisOverlay(true);
    updateConstructionAnalysisVisibility(false);
    setConstructionAnalysisOverlay(false);
  }, [
    exitStreetView,
    ensureSatelliteView,
    isSatelliteView,
    overlaysActive,
    updateRoofAnalysisVisibility,
    updateConstructionAnalysisVisibility
  ]);

  const closeRoofAnalysis = useCallback(() => {
    setRoofAnalysisOverlay(false);
    updateRoofAnalysisVisibility(false);
  }, [updateRoofAnalysisVisibility]);

  const stopRoofAnalysisOverlay = useCallback(() => {
    setRoofAnalysisOverlay(false);
  }, []);

  const openConstructionAnalysis = useCallback(() => {
    if (overlaysActive) {
      return;
    }
    updateConstructionAnalysisVisibility(true);
    setConstructionAnalysisOverlay(true);
    updateRoofAnalysisVisibility(false);
    setRoofAnalysisOverlay(false);
  }, [
    overlaysActive,
    updateConstructionAnalysisVisibility,
    updateRoofAnalysisVisibility
  ]);

  const closeConstructionAnalysis = useCallback(() => {
    setConstructionAnalysisOverlay(false);
    updateConstructionAnalysisVisibility(false);
  }, [updateConstructionAnalysisVisibility]);

  const stopConstructionAnalysisOverlay = useCallback(() => {
    setConstructionAnalysisOverlay(false);
  }, []);

  const getLatLngLiteral = useCallback(
    (
      value: google.maps.LatLngLiteral | google.maps.LatLng | null | undefined
    ) => {
      if (!value) return null;
      if (typeof (value as google.maps.LatLngLiteral).lat === "number") {
        return value as google.maps.LatLngLiteral;
      }
      const latLng = value as google.maps.LatLng;
      return { lat: latLng.lat(), lng: latLng.lng() };
    },
    []
  );

  const openContextMenu = useCallback(
    (
      latLngInput:
        | google.maps.LatLngLiteral
        | google.maps.LatLng
        | null
        | undefined,
      domEvent?: MouseEvent | PointerEvent
    ) => {
      const latLng = getLatLngLiteral(latLngInput);
      if (!latLng) return;

      if (!floodZoneEnabled && sloshActive) {
        return;
      }

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

      setContextMenu({ latLng, position });
    },
    [floodZoneEnabled, getLatLngLiteral, mapContainerRef, sloshActive]
  );

  useEffect(() => {
    return () => {
      streetViewListenerRef.current?.remove();
      streetViewListenerRef.current = null;
      streetViewRef.current = null;
    };
  }, []);

  const { imagery, status, error } = useEagleViewImagery(
    highResEnabled,
    center
  );

  const overlayImagery = useMemo(() => {
    if (!highResEnabled || status !== "ready") return null;
    return imagery;
  }, [highResEnabled, imagery, status]);

  const layers = useMemo(() => {
    const result = [];
    if (overlayImagery) {
      result.push(
        EagleViewOverlay({
          id: "eagleview-layer",
          imagery: overlayImagery,
          visible: highResEnabled
        })
      );
    }
    return result;
  }, [overlayImagery, highResEnabled]);

  // Calculate polygon area using the shoelace formula
  const calculatePolygonArea = (
    points: google.maps.LatLngLiteral[]
  ): number => {
    if (points.length < 3) return 0;

    // Convert degrees to meters using approximate conversion
    // This is a simplified calculation - for precise measurements, you'd use geodesic calculations
    const earthRadius = 6371000; // meters
    const degToRad = Math.PI / 180;

    // Calculate area using shoelace formula with spherical approximation
    let area = 0;
    for (let i = 0; i < points.length; i++) {
      const j = (i + 1) % points.length;
      const xi =
        points[i].lng *
        degToRad *
        earthRadius *
        Math.cos(points[i].lat * degToRad);
      const yi = points[i].lat * degToRad * earthRadius;
      const xj =
        points[j].lng *
        degToRad *
        earthRadius *
        Math.cos(points[j].lat * degToRad);
      const yj = points[j].lat * degToRad * earthRadius;
      area += xi * yj - xj * yi;
    }
    return Math.abs(area) / 2;
  };

  // Check if a point is close to the first point (for auto-snap)
  const isCloseToStart = (
    point: google.maps.LatLngLiteral,
    threshold: number = 0.00001
  ): boolean => {
    if (polygonPoints.length < 3) return false;
    const startPoint = polygonPoints[0];
    const distance = Math.sqrt(
      Math.pow(point.lat - startPoint.lat, 2) +
        Math.pow(point.lng - startPoint.lng, 2)
    );
    return distance < threshold;
  };

  // Calculate distance between two points using the Haversine formula
  const calculateDistance = (
    point1: google.maps.LatLngLiteral,
    point2: google.maps.LatLngLiteral
  ): number => {
    const earthRadius = 6371000; // meters
    const degToRad = Math.PI / 180;

    const lat1Rad = point1.lat * degToRad;
    const lat2Rad = point2.lat * degToRad;
    const deltaLatRad = (point2.lat - point1.lat) * degToRad;
    const deltaLngRad = (point2.lng - point1.lng) * degToRad;

    const a =
      Math.sin(deltaLatRad / 2) * Math.sin(deltaLatRad / 2) +
      Math.cos(lat1Rad) *
        Math.cos(lat2Rad) *
        Math.sin(deltaLngRad / 2) *
        Math.sin(deltaLngRad / 2);

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

  // Combined ESC key handler for context menu, measurement modes, and completed measurements
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        console.log("ESC pressed", {
          measureMode,
          distanceMode,
          polygonArea: !!polygonArea,
          distance: !!distance,
          contextMenu: !!contextMenu
        });

        // Clear completed area measurement
        if (polygonArea !== null) {
          console.log("Clearing completed area measurement");
          event.preventDefault();
          event.stopPropagation();
          setPolygonArea(null);
          setPolygonPoints([]);
          return;
        }

        // Clear completed distance measurement
        if (distance !== null) {
          console.log("Clearing completed distance measurement");
          event.preventDefault();
          event.stopPropagation();
          setDistance(null);
          setDistancePoints([]);
          return;
        }

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

        if (roofAnalysisOverlay) {
          console.log("Stopping roof analysis overlay");
          event.preventDefault();
          event.stopPropagation();
          stopRoofAnalysisOverlay();
        }
        if (constructionAnalysisOverlay) {
          console.log("Stopping construction analysis overlay");
          event.preventDefault();
          event.stopPropagation();
          stopConstructionAnalysisOverlay();
        }
      }
    };

    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
    };
  }, [
    measureMode,
    distanceMode,
    contextMenu,
    polygonArea,
    distance,
    roofAnalysisOverlay,
    constructionAnalysisOverlay,
    stopRoofAnalysisOverlay,
    stopConstructionAnalysisOverlay
  ]);

  // Only cleanup polygon data when explicitly requested via ESC or Clear button
  // Don't auto-clear when measureMode becomes false, as we want to show the completed polygon

  // Only cleanup distance data when explicitly requested via ESC or Clear button
  // Don't auto-clear when distanceMode becomes false, as we want to show the result

  const syncMapTypeId = useCallback(
    (map: google.maps.Map | undefined) => {
      if (!map) return;
      mapInstanceRef.current = map;
      const nextType = map.getMapTypeId?.() ?? "roadmap";
      setMapTypeId(nextType);

      const streetView = map.getStreetView?.();
      streetViewRef.current = streetView ?? null;
      if (streetView) {
        setStreetViewVisible(streetView.getVisible());
        streetViewListenerRef.current?.remove();
        streetViewListenerRef.current = streetView.addListener(
          "visible_changed",
          () => {
            const visible = streetView.getVisible();
            setStreetViewVisible(visible);
            if (!visible) {
              stopConstructionAnalysisOverlay();
              updateConstructionAnalysisVisibility(false);
              setContextMenu(null);
            } else {
              updateRoofAnalysisVisibility(false);
              setRoofAnalysisOverlay(false);
            }
          }
        );
      }

      if (nextType !== "satellite" && nextType !== "hybrid") {
        stopRoofAnalysisOverlay();
      }
    },
    [
      stopRoofAnalysisOverlay,
      stopConstructionAnalysisOverlay,
      updateConstructionAnalysisVisibility,
      updateRoofAnalysisVisibility
    ]
  );

  const handleMapTypeIdChanged = useCallback(
    (event: { map: google.maps.Map }) => {
      syncMapTypeId(event.map);
    },
    [syncMapTypeId]
  );

  const handleTilesLoaded = useCallback(
    (event: { map: google.maps.Map }) => {
      syncMapTypeId(event.map);
    },
    [syncMapTypeId]
  );

  const handleMapTypeChange = useCallback(
    (nextType: google.maps.MapTypeId) => {
      mapInstanceRef.current?.setMapTypeId(nextType);
      setMapTypeId(nextType);
      if (nextType !== "satellite" && nextType !== "hybrid") {
        stopRoofAnalysisOverlay();
        stopConstructionAnalysisOverlay();
      }
    },
    [stopRoofAnalysisOverlay, stopConstructionAnalysisOverlay]
  );

  return (
    <div ref={mapContainerRef} className="relative h-screen w-full">
      <MapControls
        highResEnabled={highResEnabled}
        onHighResToggle={handleHighResToggle}
        floodZoneEnabled={floodZoneEnabled}
        onFloodZoneToggle={setFloodZoneEnabled}
        femaStructuresEnabled={femaStructuresEnabled}
        onFemaStructuresToggle={setFemaStructuresEnabled}
        sloshEnabled={sloshEnabled}
        onSloshToggle={(category, enabled) =>
          setSloshEnabled((prev) => ({ ...prev, [category]: enabled }))
        }
        mapTypeId={mapTypeId}
        onMapTypeChange={handleMapTypeChange}
        isSatelliteView={isSatelliteView}
        isStreetViewActive={streetViewVisible}
        overlaysActive={overlaysActive}
        onRoofAnalysis={openRoofAnalysis}
        onConstructionAnalysis={openConstructionAnalysis}
        roofAnalysisActive={roofAnalysisVisible || roofAnalysisOverlay}
        constructionAnalysisActive={
          constructionAnalysisVisible || constructionAnalysisOverlay
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
          position: google.maps.ControlPosition.BOTTOM_CENTER
        }}
        mapTypeControl={false}
        mapTypeId={mapTypeId as google.maps.MapTypeId}
        fullscreenControl={false}
        onTilesLoaded={handleTilesLoaded}
        onMapTypeIdChanged={handleMapTypeIdChanged}
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
              console.log(
                `Polygon area: ${area.toLocaleString()} square meters`
              );
              console.log(
                `Polygon area: ${(area * 0.000247105).toFixed(2)} acres`
              );
              return;
            }

            // Add point to polygon
            setPolygonPoints((prev) => [...prev, clickedLatLng]);
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
          const clickedLatLng = event.detail.latLng;
          if (!clickedLatLng) return;

          openContextMenu(
            clickedLatLng,
            event.domEvent as MouseEvent | PointerEvent | undefined
          );
        }}
      >
        <FloodZoneOverlay enabled={floodZoneEnabled} />
        <FemaStructuresOverlay enabled={femaStructuresEnabled} />
        <SloshOverlay
          enabledCategories={SLOSH_CATEGORIES.filter(
            (category) => sloshEnabled[category]
          )}
        />

        {/* Render measurement polygon using custom component */}
        <MeasurementPolygon
          points={polygonPoints}
          area={polygonArea ?? undefined}
        />

        {/* Render distance measurement using custom component */}
        <DistanceMeasurement
          points={distancePoints}
          distance={distance ?? undefined}
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
      {(roofAnalysisVisible || roofAnalysisOverlay) && (
        <RoofAnalysis
          overlayActive={roofAnalysisOverlay && isSatelliteView}
          visible={roofAnalysisVisible}
          mapContainerRef={mapContainerRef}
          onExit={closeRoofAnalysis}
          onOverlayCancel={stopRoofAnalysisOverlay}
          onRequestDraw={openRoofAnalysis}
          panelContainerRef={roofAnalysisPanelRef}
          isSatelliteView={isSatelliteView}
        />
      )}
      {(constructionAnalysisVisible || constructionAnalysisOverlay) && (
        <ConstructionAnalysis
          overlayActive={constructionAnalysisOverlay}
          visible={constructionAnalysisVisible}
          mapContainerRef={mapContainerRef}
          onExit={closeConstructionAnalysis}
          onOverlayCancel={stopConstructionAnalysisOverlay}
          onRequestDraw={openConstructionAnalysis}
          panelContainerRef={constructionAnalysisPanelRef}
          isStreetViewVisible={streetViewVisible}
        />
      )}
      {(() => {
        const sloshVisible = sloshActive;
        const showAnyLegend = floodZoneEnabled || sloshVisible;

        if (!showAnyLegend) {
          return null;
        }

        return (
          <div className="pointer-events-none absolute bottom-4 right-4 z-20 flex flex-col items-end gap-3">
            {sloshVisible && (
              <SloshLegend
                enabledCategories={sloshEnabled}
                className="relative pointer-events-auto"
              />
            )}
            {floodZoneEnabled && (
              <FloodZoneLegend className="relative pointer-events-auto" />
            )}
          </div>
        );
      })()}

      {/* Area measurement result display - top center */}
      {polygonArea !== null && distance === null && (
        <div
          className="absolute left-1/2 z-20 -translate-x-1/2 rounded-md border border-slate-200 bg-white p-3 shadow-lg"
          style={{ top: "5px" }}
        >
          <div className="text-sm font-medium text-slate-700">
            Area Measurement
          </div>
          <div className="text-lg font-bold text-slate-900">
            {Math.round(polygonArea).toLocaleString()} m²
          </div>
          <div className="text-sm text-slate-600">
            {Math.round(polygonArea * 10.764).toLocaleString()} ft²
          </div>
          <div className="text-sm text-slate-600">
            {Math.round(polygonArea * 0.000247105 * 100) / 100} acres
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

      {/* Distance measurement result display - top center */}
      {distance !== null && polygonArea === null && (
        <div
          className="absolute left-1/2 z-20 -translate-x-1/2 rounded-md border border-slate-200 bg-white p-3 shadow-lg"
          style={{ top: "5px" }}
        >
          <div className="text-sm font-medium text-slate-700">
            Distance Measurement
          </div>
          <div className="text-lg font-bold text-slate-900">
            {Math.round(distance)} m
          </div>
          <div className="text-sm text-slate-600">
            {Math.round(distance * 3.28084)} ft
          </div>
          {distance >= 1000 && (
            <div className="text-sm text-slate-600">
              {Math.round((distance / 1000) * 100) / 100} km /{" "}
              {Math.round(distance * 0.000621371 * 100) / 100} mi
            </div>
          )}
          <button
            onClick={() => {
              setDistance(null);
              setDistancePoints([]);
            }}
            className="mt-2 text-xs text-slate-500 hover:text-slate-700"
          >
            Clear
          </button>
        </div>
      )}

      {/* Measurement instructions */}
      {measureMode && (
        <div
          className="absolute left-1/2 z-20 -translate-x-1/2 rounded-md border border-slate-200 bg-white p-3 shadow-lg"
          style={{ top: "80px" }}
        >
          <div className="text-sm text-slate-700">
            {polygonPoints.length === 0 &&
              "Click on the map to start drawing a polygon"}
            {polygonPoints.length === 1 && "Continue clicking to add points"}
            {polygonPoints.length === 2 &&
              "Add at least one more point to create a polygon"}
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
        <div
          className="absolute left-1/2 z-20 -translate-x-1/2 rounded-md border border-slate-200 bg-white p-3 shadow-lg"
          style={{ top: "80px" }}
        >
          <div className="text-sm text-slate-700">
            {distancePoints.length === 0 &&
              "Click on the map to select the first point"}
            {distancePoints.length === 1 &&
              "Click on the map to select the second point"}
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
          {!floodZoneEnabled &&
            !SLOSH_CATEGORIES.some((category) => sloshEnabled[category]) && (
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
                    <button
                      className="block w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400"
                      disabled={!isSatelliteView}
                      onClick={() => {
                        if (!isSatelliteView) {
                          return;
                        }
                        openRoofAnalysis();
                        setContextMenu(null);
                      }}
                      title={
                        isSatelliteView
                          ? undefined
                          : "Switch to Satellite view to use roof analysis"
                      }
                    >
                      🏠 Roof Analysis
                    </button>
                    <button
                      className="block w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
                      onClick={() => {
                        openConstructionAnalysis();
                        setContextMenu(null);
                      }}
                    >
                      🏢 Construction Analysis
                    </button>
                    {!isSatelliteView && (
                      <div className="px-4 pb-1 pt-1 text-xs text-slate-400">
                        Switch to Satellite map view to enable roof analysis
                      </div>
                    )}
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
                          console.log(
                            `Polygon area: ${area.toLocaleString()} square meters`
                          );
                          console.log(
                            `Polygon area: ${(area * 0.000247105).toFixed(
                              2
                            )} acres`
                          );
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
