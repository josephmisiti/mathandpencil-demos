import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { BitmapLayer } from "@deck.gl/layers";
import { TileLayer } from "@deck.gl/geo-layers";
import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useMemo, useState } from "react";

type SloshOverlayProps = {
  enabledCategories: string[];
};

const TILE_URL =
  "http://localhost:3005/tiles/slosh/{z}/{x}/{y}?category={category}";

function loadRasterTile(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = (err) => reject(err);
    image.src = url;
  });
}

export default function SloshOverlay({ enabledCategories }: SloshOverlayProps) {
  const map = useMap();
  const [overlay, setOverlay] = useState<GoogleMapsOverlay | null>(null);

  useEffect(() => {
    if (!map) return;

    const instance = new GoogleMapsOverlay({ layers: [] });
    instance.setMap(map);
    setOverlay(instance);

    return () => {
      instance.setMap(null);
    };
  }, [map]);

  const layers = useMemo(() => {
    if (!enabledCategories.length) return [];

    return enabledCategories.map(
      (category) =>
        new TileLayer({
          id: `slosh-${category}`,
        minZoom: 8,
        maxZoom: 14,
          tileSize: 256,
          getTileData: (tile: any) => {
            const x = tile?.x ?? tile?.tile?.x ?? tile?.index?.x;
            const y = tile?.y ?? tile?.tile?.y ?? tile?.index?.y;
            const z = tile?.z ?? tile?.tile?.z ?? tile?.index?.z;

            if (
              typeof x !== "number" ||
              typeof y !== "number" ||
              typeof z !== "number"
            ) {
              return Promise.resolve(null);
            }

            const url = TILE_URL.replace("{category}", category)
              .replace("{z}", String(z))
              .replace("{x}", String(x))
              .replace("{y}", String(y));

            console.info(`Loading SLOSH tile: ${url}`);

            return loadRasterTile(url);
          },
          renderSubLayers: (props) => {
            const { data, tile } = props;
            if (!data) return null;

            const bbox = tile?.bbox ?? tile?.boundingBox;
            let boundsArray: [number, number, number, number] | null = null;

            if (Array.isArray(bbox)) {
              if (bbox.length === 4 && typeof bbox[0] === "number") {
                const arr = bbox as unknown as number[];
                boundsArray = [arr[0], arr[1], arr[2], arr[3]];
              } else if (
                bbox.length === 2 &&
                Array.isArray(bbox[0]) &&
                Array.isArray(bbox[1])
              ) {
                const [[minX, minY], [maxX, maxY]] = bbox as unknown as [
                  number[],
                  number[]
                ];
                boundsArray = [minX, minY, maxX, maxY];
              }
            }

            if (!boundsArray) {
              return null;
            }

            const [minX, minY, maxX, maxY] = boundsArray;

            return new BitmapLayer(props, {
              image: data,
              bounds: [minX, minY, maxX, maxY],
              opacity: 0.65
            });
          }
        })
    );
  }, [enabledCategories]);

  useEffect(() => {
    if (!overlay) return;
    overlay.setProps({ layers });
  }, [overlay, layers]);

  return null;
}
