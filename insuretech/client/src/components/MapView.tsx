import { useEffect, useMemo, useRef, useState } from "react";
import { Map, Marker, InfoWindow } from "@vis.gl/react-google-maps";
import { MapProps, Location } from "../types/location";
import MarkerInfo from "./MarkerInfo";
import MapControls from "./MapControls";
import { useEagleViewImagery } from "../hooks/useEagleViewImagery";
import EagleViewOverlay from "./EagleViewOverlay";
import FloodZoneOverlay from "./FloodZoneOverlay";
import FloodZoneLegend from "./FloodZoneLegend";

export default function MapView({
  center,
  markers,
  zoom = 12,
  onViewChange
}: MapProps) {
  const [selectedMarker, setSelectedMarker] = useState<Location | null>(null);
  const [highResEnabled, setHighResEnabled] = useState(false);
  const [floodZoneEnabled, setFloodZoneEnabled] = useState(false);
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

  const { imagery, status, error } = useEagleViewImagery(
    highResEnabled,
    center
  );

  const overlayImagery = useMemo(() => {
    if (!highResEnabled || status !== "ready") return null;
    return imagery;
  }, [highResEnabled, imagery, status]);

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

  useEffect(() => {
    if (!contextMenu) return;

    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setContextMenu(null);
      }
    };

    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
    };
  }, [contextMenu]);

  return (
    <div ref={mapContainerRef} className="relative h-screen w-screen">
      <MapControls
        highResEnabled={highResEnabled}
        onHighResToggle={handleHighResToggle}
        floodZoneEnabled={floodZoneEnabled}
        onFloodZoneToggle={setFloodZoneEnabled}
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
          position: google.maps.ControlPosition.RIGHT_CENTER
        }}
        streetViewControl={true}
        streetViewControlOptions={{
          position: google.maps.ControlPosition.RIGHT_CENTER
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
        onClick={() => setContextMenu(null)}
        onContextmenu={(event) => {
          if (!floodZoneEnabled) return;

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
      {floodZoneEnabled && <FloodZoneLegend />}
      {contextMenu && (
        <div
          className="absolute z-30 min-w-[180px] rounded-md border border-slate-200 bg-white py-1 shadow-lg"
          style={{ left: contextMenu.position.x, top: contextMenu.position.y }}
          onClick={(event) => event.stopPropagation()}
        >
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
        </div>
      )}
    </div>
  );
}
