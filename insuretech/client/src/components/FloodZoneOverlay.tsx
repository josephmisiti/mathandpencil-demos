import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { MVTLayer, GeoJsonLayer } from "deck.gl";
import { MVTLoader } from "@loaders.gl/mvt";
import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";

type FloodZoneOverlayProps = {
  enabled: boolean;
};

const TILE_URL = "http://localhost:3005/tiles/{z}/{x}/{y}";

// Styling function for the flood zone polygons
const getFillColor = (d: any) => {
  const zone = d.properties.FLD_ZONE;
  switch (zone) {
    case "A":
    case "AE":
    case "AH":
    case "AO":
      return [59, 130, 246, 180]; // blue-500 with opacity
    case "V":
    case "VE":
      return [239, 68, 68, 190]; // red-500 with opacity
    case "X":
      if (d.properties.ZONE_SUBTY?.includes("0.2")) {
        return [249, 115, 22, 160]; // orange-500 with opacity
      }
      return [0, 0, 0, 0]; // Do not render minimal flood hazard 'X' zones
    default:
      return [168, 162, 158, 130]; // stone-400 with opacity for other zones
  }
};

export default function FloodZoneOverlay({ enabled }: FloodZoneOverlayProps) {
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
            id: "flood-zones",
            data: TILE_URL,
            binary: true,
            minZoom: 0,
            maxZoom: 18,
            getFillColor: getFillColor,
            stroked: false,
            filled: true,
            // Explicitly use MVTLoader and render with GeoJsonLayer
            loaders: [MVTLoader],
            renderSubLayers: (props) => {
              // Simplified to match working example
              return new GeoJsonLayer(props);
            },
          }),
        ]
      : [];

    overlay.setProps({ layers });
  }, [overlay, enabled]);

  return null;
}