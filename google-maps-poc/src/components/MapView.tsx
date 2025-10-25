import {useState} from 'react';
import {Map, Marker} from '@vis.gl/react-google-maps';
import type {Location, MapProps} from '../types/location';
import MarkerInfo from './MarkerInfo';

const MapView: React.FC<MapProps> = ({center, markers, zoom = 12}) => {
  const [selected, setSelected] = useState<Location | null>(null);
  return (
    <div className="w-full h-96">
      <Map center={{lat: center.lat, lng: center.lng}} zoom={zoom} style={{width: '100%', height: '100%'}}>
        {markers.map(m => (
          <Marker
            key={m.placeId || m.address}
            position={{lat: m.lat, lng: m.lng}}
            onClick={() => setSelected(m)}
          />
        ))}
        {selected && <MarkerInfo location={selected} onClose={() => setSelected(null)} />}
      </Map>
    </div>
  );
};

export default MapView;
