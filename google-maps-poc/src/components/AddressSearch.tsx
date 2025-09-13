import {useState} from 'react';
import PlacesAutocomplete, {geocodeByAddress, getLatLng} from 'react-places-autocomplete';
import type {Location} from '../types/location';

interface Props {
  onSelect: (loc: Location) => void;
}

const AddressSearch: React.FC<Props> = ({onSelect}) => {
  const [address, setAddress] = useState('');

  const handleSelect = async (val: string, placeId: string | null) => {
    setAddress(val);
    try {
      const results = await geocodeByAddress(val);
      const {lat, lng} = await getLatLng(results[0]);
      onSelect({lat, lng, address: val, placeId: placeId || undefined});
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <PlacesAutocomplete value={address} onChange={setAddress} onSelect={handleSelect}>
      {({
        getInputProps,
        suggestions,
        getSuggestionItemProps,
        loading,
      }: any) => (
        <div className="w-full max-w-md mx-auto relative">
          <input
            {...getInputProps({
              placeholder: 'Search for an address...',
              className: 'w-full p-2 border rounded'
            })}
          />
          {suggestions.length > 0 && (
            <div className="absolute z-10 w-full bg-white border rounded shadow mt-1">
              {loading && <div className="p-2">Loading...</div>}
              {suggestions.map((s: any) => (
                <div
                  key={s.placeId}
                  {...getSuggestionItemProps(s, {
                    className: 'p-2 cursor-pointer hover:bg-gray-100'
                  })}
                >
                  {s.description}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </PlacesAutocomplete>
  );
};

export default AddressSearch;
