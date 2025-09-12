import { useState } from 'react';
import { Map, Marker, InfoWindow } from '@vis.gl/react-google-maps';
import { MapProps, Location } from '../types/location';
import MarkerInfo from './MarkerInfo';
import MapControls from './MapControls';

export default function MapView({ center, markers, zoom = 12 }: MapProps) {
  const [selectedMarker, setSelectedMarker] = useState<Location | null>(null);
  const [highResEnabled, setHighResEnabled] = useState(false);

  const handleHighResToggle = (enabled: boolean) => {
    setHighResEnabled(enabled);
    console.log('High res imagery:', enabled);
  };

  return (
    <div className="w-screen h-screen relative">
      <MapControls onHighResToggle={handleHighResToggle} />
      <Map
        zoom={zoom}
        center={center}
        gestureHandling={'auto'}
        disableDefaultUI={true}
        options={{
          zoomControl: true,
          zoomControlOptions: {
            position: google.maps.ControlPosition.RIGHT_CENTER
          },
          streetViewControl: true,
          streetViewControlOptions: {
            position: google.maps.ControlPosition.RIGHT_CENTER
          },
          mapTypeControl: true,
          mapTypeControlOptions: {
            position: google.maps.ControlPosition.LEFT_BOTTOM
          },
          fullscreenControl: false
        }}
      >
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