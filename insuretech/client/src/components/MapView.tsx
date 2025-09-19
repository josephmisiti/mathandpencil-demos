import { useEffect, useMemo, useRef, useState } from "react";
import { Map, Marker, InfoWindow } from "@vis.gl/react-google-maps";
import { MapProps, Location } from "../types/location";
import MarkerInfo from "./MarkerInfo";
import MapControls from "./MapControls";
import { useEagleViewImagery } from "../hooks/useEagleViewImagery";
import EagleViewOverlay from "./EagleViewOverlay";
import FloodZoneOverlay from "./FloodZoneOverlay";

export default function MapView({
  center,
  markers,
  zoom = 12,
  onViewChange
}: MapProps) {
  const [selectedMarker, setSelectedMarker] = useState<Location | null>(null);
  const [highResEnabled, setHighResEnabled] = useState(false);
  const [floodZoneEnabled, setFloodZoneEnabled] = useState(true);
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

  return (
    <div className="w-screen h-screen relative">
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
    </div>
  );
}
