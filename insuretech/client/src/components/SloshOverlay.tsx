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

const CATEGORY_COLORS: Record<string, [number, number, number]> = {
  Category1: [59, 130, 246],
  Category2: [147, 51, 234],
  Category3: [249, 115, 22],
  Category4: [16, 185, 129],
  Category5: [239, 68, 68]
};

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
            if (!data || !tile) {
              return null;
            }

            const bbox = tile.bbox ?? tile.boundingBox;

            let bounds: [number, number, number, number] | null = null;

            if (bbox) {
              if (Array.isArray(bbox)) {
                if (bbox.length === 4 && typeof bbox[0] === "number") {
                  const [minX, minY, maxX, maxY] = bbox as unknown as [
                    number,
                    number,
                    number,
                    number
                  ];
                  bounds = [minX, minY, maxX, maxY];
                } else if (
                  bbox.length === 2 &&
                  Array.isArray(bbox[0]) &&
                  Array.isArray(bbox[1])
                ) {
                  const [[minX, minY], [maxX, maxY]] = bbox as unknown as [
                    number[],
                    number[]
                  ];
                  bounds = [minX, minY, maxX, maxY];
                }
              } else if (
                typeof bbox === "object" &&
                "west" in bbox &&
                "south" in bbox &&
                "east" in bbox &&
                "north" in bbox
              ) {
                const { west, south, east, north } = bbox as {
                  west: number;
                  south: number;
                  east: number;
                  north: number;
                };
                bounds = [west, south, east, north];
              }
            }

            if (!bounds) {
              return null;
            }

            const tintColor = CATEGORY_COLORS[category] ?? [255, 255, 255];

            return new BitmapLayer(props, {
              image: data,
              bounds,
              data: null,
              opacity: 0.65,
              tintColor,
              transparentColor: [0, 0, 0, 0]
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
