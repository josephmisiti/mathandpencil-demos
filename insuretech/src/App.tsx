import { useState, useEffect } from 'react';
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
  const [initialAddress, setInitialAddress] = useState('');

  // Read URL parameters on mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const lat = urlParams.get('lat');
    const lng = urlParams.get('lng');
    const address = urlParams.get('address');

    if (lat && lng && address) {
      const decodedAddress = decodeURIComponent(address);
      const location: Location = {
        lat: parseFloat(lat),
        lng: parseFloat(lng),
        address: decodedAddress,
      };
      setMapCenter(location);
      setMarkers([location]);
      setInitialAddress(decodedAddress);
    }
  }, []);

  const handleLocationSelect = (location: Location) => {
    setMapCenter(location);
    setMarkers([location]);
    
    // Update URL parameters
    const url = new URL(window.location.href);
    url.searchParams.set('lat', location.lat.toString());
    url.searchParams.set('lng', location.lng.toString());
    url.searchParams.set('address', encodeURIComponent(location.address));
    window.history.pushState({}, '', url.toString());
  };

  const handleAddressClear = () => {
    setMapCenter(DEFAULT_CENTER);
    setMarkers([]);
    
    // Clear URL parameters
    const url = new URL(window.location.href);
    url.searchParams.delete('lat');
    url.searchParams.delete('lng');
    url.searchParams.delete('address');
    window.history.pushState({}, '', url.toString());
  };

  return (
    <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
      <div className="relative w-screen h-screen">
        <MapView center={mapCenter} markers={markers} />
        
        <div className="absolute top-4 left-4 z-10 w-80">
          <AddressSearch 
            onLocationSelect={handleLocationSelect}
            onAddressClear={handleAddressClear}
            initialAddress={initialAddress}
          />
        </div>
      </div>
    </APIProvider>
  );
}

export default App;