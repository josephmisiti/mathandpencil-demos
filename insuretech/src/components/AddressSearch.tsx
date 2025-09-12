import { useState } from 'react';
import PlacesAutocomplete, {
  geocodeByAddress,
  getLatLng,
} from 'react-places-autocomplete';
import { AddressSearchProps, Location } from '../types/location';

export default function AddressSearch({ onLocationSelect }: AddressSearchProps) {
  const [address, setAddress] = useState('');

  const handleSelect = async (selectedAddress: string) => {
    try {
      const results = await geocodeByAddress(selectedAddress);
      const latLng = await getLatLng(results[0]);
      
      const location: Location = {
        lat: latLng.lat,
        lng: latLng.lng,
        address: selectedAddress,
        placeId: results[0].place_id,
      };

      onLocationSelect(location);
      setAddress(selectedAddress);
    } catch (error) {
      console.error('Error selecting address:', error);
    }
  };

  return (
    <div className="w-full max-w-lg">
      <PlacesAutocomplete
        value={address}
        onChange={setAddress}
        onSelect={handleSelect}
      >
        {({ getInputProps, suggestions, getSuggestionItemProps, loading }) => (
          <div className="relative">
            <input
              {...getInputProps({
                placeholder: 'Search for an address...',
                className:
                  'w-full px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              })}
            />
            {(loading || suggestions.length > 0) && (
              <div className="absolute z-10 w-full bg-white border border-gray-300 rounded-lg shadow-lg mt-1 max-h-60 overflow-y-auto">
                {loading && (
                  <div className="px-4 py-2 text-gray-500">Loading...</div>
                )}
                {suggestions.map((suggestion) => {
                  const className = suggestion.active
                    ? 'px-4 py-2 bg-blue-100 cursor-pointer hover:bg-blue-200'
                    : 'px-4 py-2 cursor-pointer hover:bg-gray-100';

                  return (
                    <div
                      {...getSuggestionItemProps(suggestion, {
                        className,
                      })}
                      key={suggestion.placeId}
                    >
                      <span>{suggestion.description}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </PlacesAutocomplete>
    </div>
  );
}