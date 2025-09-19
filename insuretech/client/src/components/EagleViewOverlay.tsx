import { useEffect, useRef } from 'react';
import { useMap } from '@vis.gl/react-google-maps';
import type { EagleViewImagery } from '../services/eagleView';
import { buildTileUrl } from '../services/eagleView';

type EagleViewOverlayProps = {
  enabled: boolean;
  imagery: EagleViewImagery | null;
};

export default function EagleViewOverlay({enabled, imagery}: EagleViewOverlayProps) {
  const map = useMap();
  const overlayRef = useRef<google.maps.ImageMapType | null>(null);

  useEffect(() => {
    if (!map) return;

    const removeOverlay = () => {
      if (!overlayRef.current) return;
      const overlays = map.overlayMapTypes;
      for (let i = overlays.getLength() - 1; i >= 0; i -= 1) {
        const existing = overlays.getAt(i);
        if (existing === overlayRef.current) {
          overlays.removeAt(i);
        }
      }
      overlayRef.current = null;
    };

    if (!enabled || !imagery) {
      removeOverlay();
      return removeOverlay;
    }

    removeOverlay();

    const mapType = new google.maps.ImageMapType({
      name: 'EagleView High Res',
      tileSize: new google.maps.Size(256, 256),
      minZoom: imagery.minZoom,
      maxZoom: imagery.maxZoom,
      opacity: 1,
      getTileUrl: (coord, zoom) =>
        buildTileUrl(imagery.tileUrlTemplate, imagery.imageUrn, zoom, coord.x, coord.y)
    });

    overlayRef.current = mapType;
    map.overlayMapTypes.push(mapType);

    return removeOverlay;
  }, [enabled, imagery, map]);

  return null;
}
