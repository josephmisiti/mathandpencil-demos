import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { MVTLayer, GeoJsonLayer } from "deck.gl";
import { MVTLoader } from "@loaders.gl/mvt";
import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";

type FemaStructuresOverlayProps = {
  enabled: boolean;
};

const TILE_URL = "http://localhost:3005/tiles/fema_structures/{z}/{x}/{y}";

// Styling function for FEMA structures
const getFillColor = (d: any) => {
  // Use a distinct color for FEMA structures - purple/violet
  return [147, 51, 234, 180]; // violet-600 with opacity
};

export default function FemaStructuresOverlay({ enabled }: FemaStructuresOverlayProps) {
  const map = useMap();
  const [overlay, setOverlay] = useState<GoogleMapsOverlay | null>(null);

  // Effect for creating and cleaning up the overlay
  useEffect(() => {
    if (!map) return;

    const instance = new GoogleMapsOverlay({ layers: [] });
    instance.setMap(map);
    setOverlay(instance);

    return () => {
      instance.setMap(null);
    };
  }, [map]);

  // Effect for updating layers based on the 'enabled' prop
  useEffect(() => {
    if (!overlay) return;

    const layers = enabled
      ? [
          new MVTLayer({
            id: "fema-structures",
            data: TILE_URL,
            binary: true,
            minZoom: 0,
            maxZoom: 18,
            getFillColor: getFillColor as any,
            stroked: false,
            filled: true,
            loaders: [MVTLoader],
            renderSubLayers: (props) => {
              return new GeoJsonLayer(props);
            }
          })
        ]
      : [];

    overlay.setProps({ layers });
  }, [overlay, enabled]);

  return null;
}
