export type Location = {
  lat: number;
  lng: number;
  address: string;
  placeId?: string;
}

export type MapProps = {
  center: Location;
  markers: Location[];
  zoom?: number;
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