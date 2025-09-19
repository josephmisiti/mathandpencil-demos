export type Location = {
  lat: number;
  lng: number;
  address: string;
  placeId?: string;
}

export type LatLngLiteral = {
  lat: number;
  lng: number;
};

export type MapProps = {
  center: Location;
  markers: Location[];
  zoom?: number;
  onViewChange?: (view: { center: LatLngLiteral; zoom: number }) => void;
}

export type MarkerInfoProps = {
  location: Location;
  onClose: () => void;
}

export type AddressSearchProps = {
  onLocationSelect: (location: Location) => void;
  onAddressClear?: () => void;
  initialAddress?: string;
}
