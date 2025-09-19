import { MarkerInfoProps } from '../types/location';

export default function MarkerInfo({ location }: MarkerInfoProps) {
  return (
    <div className="p-2 max-w-xs">
      <h3 className="font-semibold text-gray-800 mb-2">Location Details</h3>
      <p className="text-sm text-gray-600 mb-1">
        <span className="font-medium">Address:</span> {location.address}
      </p>
      <p className="text-sm text-gray-600 mb-1">
        <span className="font-medium">Latitude:</span> {location.lat.toFixed(6)}
      </p>
      <p className="text-sm text-gray-600">
        <span className="font-medium">Longitude:</span> {location.lng.toFixed(6)}
      </p>
    </div>
  );
}