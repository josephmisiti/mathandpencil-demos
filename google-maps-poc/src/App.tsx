import {useState} from 'react';
import {APIProvider} from '@vis.gl/react-google-maps';
import AddressSearch from './components/AddressSearch';
import MapView from './components/MapView';
import type {Location} from './types/location';

const defaultLocation: Location = {
  lat: 37.7749,
  lng: -122.4194,
  address: 'San Francisco, CA'
};

function App() {
  const [center, setCenter] = useState<Location>(defaultLocation);
  const [markers, setMarkers] = useState<Location[]>([]);

  const handleSelect = (loc: Location) => {
    setCenter(loc);
    setMarkers([loc]);
  };

  return (
    <APIProvider apiKey={import.meta.env.VITE_GOOGLE_MAPS_API_KEY}>
      <div className="flex flex-col items-center p-4 space-y-4">
        <AddressSearch onSelect={handleSelect} />
        <MapView center={center} markers={markers} />
      </div>
    </APIProvider>
  );
}

export default App;
