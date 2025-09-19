import { useEffect, useMemo, useState } from "react";
import { Map, Marker, InfoWindow } from "@vis.gl/react-google-maps";
import { MapProps, Location } from "../types/location";
import MarkerInfo from "./MarkerInfo";
import MapControls from "./MapControls";
import { useEagleViewImagery } from "../hooks/useEagleViewImagery";
import EagleViewOverlay from "./EagleViewOverlay";

export default function MapView({ center, markers, zoom = 12 }: MapProps) {
  const [selectedMarker, setSelectedMarker] = useState<Location | null>(null);
  const [highResEnabled, setHighResEnabled] = useState(false);
  const [highResErrorMessage, setHighResErrorMessage] = useState<string | null>(null);
  const [mapZoom, setMapZoom] = useState(zoom);
  const [mapCenter, setMapCenter] = useState<google.maps.LatLngLiteral>({
    lat: center.lat,
    lng: center.lng
  });

  const { imagery, status, error } = useEagleViewImagery(highResEnabled, center);

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
  }, [zoom]);

  useEffect(() => {
    setMapCenter({lat: center.lat, lng: center.lng});
  }, [center.lat, center.lng]);

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
        onZoomChanged={(event) => setMapZoom(event.detail.zoom)}
        onCenterChanged={(event) => setMapCenter(event.detail.center)}
      >
        <EagleViewOverlay enabled={!!overlayImagery} imagery={overlayImagery} />
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
