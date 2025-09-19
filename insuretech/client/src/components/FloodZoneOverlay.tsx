import { useEffect, useRef } from "react";
import { useMap } from "@vis.gl/react-google-maps";

type FloodZoneOverlayProps = {
  enabled: boolean;
  opacity?: number;
};

const TILE_URL_TEMPLATE = "http://localhost:3005/tiles/{z}/{x}/{y}";

const buildTileUrl = (zoom: number, x: number, y: number) => {
  const tileRange = 1 << zoom;
  if (y < 0 || y >= tileRange) return "";
  const wrappedX = ((x % tileRange) + tileRange) % tileRange;

  return TILE_URL_TEMPLATE.replace("{z}", zoom.toString())
    .replace("{x}", wrappedX.toString())
    .replace("{y}", y.toString());
};

export default function FloodZoneOverlay({
  enabled,
  opacity = 0.7
}: FloodZoneOverlayProps) {
  const map = useMap();
  const overlayRef = useRef<google.maps.ImageMapType | null>(null);

  useEffect(() => {
    if (!map) return;

    const removeOverlay = () => {
      if (!overlayRef.current) return;
      const overlays = map.overlayMapTypes;
      for (let i = overlays.getLength() - 1; i >= 0; i -= 1) {
        if (overlays.getAt(i) === overlayRef.current) {
          overlays.removeAt(i);
        }
      }
      overlayRef.current = null;
    };

    if (!enabled) {
      removeOverlay();
      return removeOverlay;
    }

    removeOverlay();

    const mapType = new google.maps.ImageMapType({
      name: "Flood Zones",
      tileSize: new google.maps.Size(256, 256),
      opacity,
      getTileUrl: (coord, zoom) => buildTileUrl(zoom, coord.x, coord.y)
    });

    overlayRef.current = mapType;
    map.overlayMapTypes.push(mapType);

    return removeOverlay;
  }, [enabled, map, opacity]);

  return null;
}
