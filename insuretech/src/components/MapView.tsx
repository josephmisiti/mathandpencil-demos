import { useState } from 'react';
import { Map, Marker, InfoWindow } from '@vis.gl/react-google-maps';
import { MapProps, Location } from '../types/location';
import MarkerInfo from './MarkerInfo';

export default function MapView({ center, markers, zoom = 12 }: MapProps) {
  const [selectedMarker, setSelectedMarker] = useState<Location | null>(null);

  return (
    <div className="w-screen h-screen">
      <Map
        defaultZoom={zoom}
        defaultCenter={center}
        gestureHandling={'greedy'}
        disableDefaultUI={false}
        mapTypeControlOptions={{
          position: google.maps.ControlPosition.LEFT_BOTTOM
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