import {InfoWindow} from '@vis.gl/react-google-maps';
import type {Location} from '../types/location';

interface MarkerInfoProps {
  location: Location;
  onClose: () => void;
}

const MarkerInfo: React.FC<MarkerInfoProps> = ({location, onClose}) => (
  <InfoWindow
    position={{lat: location.lat, lng: location.lng}}
    onCloseClick={onClose}
  >
    <div className="p-2">{location.address}</div>
  </InfoWindow>
);

export default MarkerInfo;
