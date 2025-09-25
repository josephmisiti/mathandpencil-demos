import { useState, useEffect } from 'react';
import PlacesAutocomplete, {
  geocodeByAddress,
  getLatLng,
} from 'react-places-autocomplete';
import { AddressSearchProps, Location } from '../types/location';
import PdfUploadDropzone from './PdfUploadDropzone';

export default function AddressSearch({ 
  onLocationSelect, 
  onAddressClear, 
  initialAddress = '',
  hidePdfUpload = false
}: AddressSearchProps) {
  const [address, setAddress] = useState(initialAddress);

  useEffect(() => {
    setAddress(initialAddress);
  }, [initialAddress]);

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

  const handleAddressChange = (value: string) => {
    setAddress(value);
    if (value === '' && onAddressClear) {
      onAddressClear();
    }
  };

  const handleClear = () => {
    setAddress('');
    if (onAddressClear) {
      onAddressClear();
    }
  };

  const handlePdfComplete = (result: any) => {
    console.log('PDF processing completed:', result);
    // The geocoding happens automatically inside PdfUploadDropzone
    // and logs to console, no additional action needed here
  };

  return (
    <div className="w-full max-w-xl space-y-4">
      {/* Address Search Section */}
      <div>
        <PlacesAutocomplete
          value={address}
          onChange={handleAddressChange}
          onSelect={handleSelect}
        >
          {({ getInputProps, suggestions, getSuggestionItemProps, loading }) => (
            <div className="relative">
              <div className="relative">
                <input
                  {...getInputProps({
                    placeholder: 'Search for an address...',
                    className:
                      'w-full px-4 py-2 pr-10 text-gray-700 bg-white border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  })}
                />
                {address && (
                  <button
                    onClick={handleClear}
                    className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    type="button"
                  >
                    ×
                  </button>
                )}
              </div>
              {(loading || suggestions.length > 0) && (
                <div className="absolute z-20 w-full bg-white border border-gray-300 rounded-lg shadow-lg mt-1 max-h-60 overflow-y-auto">
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

      {/* PDF Upload Section - separate container to avoid event conflicts */}
      {!hidePdfUpload && (
        <div>
          <PdfUploadDropzone onComplete={handlePdfComplete} />
        </div>
      )}
    </div>
  );
}
