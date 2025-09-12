import { useState } from 'react';
import { APIProvider } from '@vis.gl/react-google-maps';
import AddressSearch from './components/AddressSearch';
import MapView from './components/MapView';
import { Location } from './types/location';

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

const DEFAULT_CENTER: Location = {
  lat: 37.7749,
  lng: -122.4194,
  address: 'San Francisco, CA, USA',
};

function App() {
  const [mapCenter, setMapCenter] = useState<Location>(DEFAULT_CENTER);
  const [markers, setMarkers] = useState<Location[]>([]);

  const handleLocationSelect = (location: Location) => {
    setMapCenter(location);
    setMarkers([location]);
  };

  return (
    <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
      <div className="relative w-screen h-screen">
        <MapView center={mapCenter} markers={markers} />
        
        <div className="absolute top-4 left-4 z-10 w-80">
          <AddressSearch onLocationSelect={handleLocationSelect} />
        </div>
      </div>
    </APIProvider>
  );
}

export default App;