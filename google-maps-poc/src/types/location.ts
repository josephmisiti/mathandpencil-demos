export interface Location {
  lat: number;
  lng: number;
  address: string;
  placeId?: string;
}

export interface MapProps {
  center: Location;
  markers: Location[];
  zoom?: number;
}
