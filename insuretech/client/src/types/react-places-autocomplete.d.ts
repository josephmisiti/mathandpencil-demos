declare module 'react-places-autocomplete' {
  export interface Suggestion {
    active: boolean;
    description: string;
    placeId: string;
  }

  export interface PlacesAutocompleteProps {
    value: string;
    onChange: (value: string) => void;
    onSelect: (value: string) => void;
    children: (props: {
      getInputProps: (options?: any) => any;
      suggestions: Suggestion[];
      getSuggestionItemProps: (suggestion: Suggestion, options?: any) => any;
      loading: boolean;
    }) => React.ReactNode;
  }

  export default function PlacesAutocomplete(props: PlacesAutocompleteProps): JSX.Element;

  export function geocodeByAddress(address: string): Promise<any[]>;
  export function getLatLng(result: any): Promise<{ lat: number; lng: number }>;
}