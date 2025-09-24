import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { BitmapLayer } from "@deck.gl/layers";
import { TileLayer } from "@deck.gl/geo-layers";
import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useMemo, useState } from "react";
import {
  SLOSH_CATEGORY_ALPHA,
  SLOSH_CATEGORY_COLORS,
  SloshCategory
} from "../constants/slosh";

type SloshOverlayProps = {
  enabledCategories: SloshCategory[];
};

const TILE_URL =
  "http://localhost:3005/tiles/slosh/{z}/{x}/{y}?category={category}";

const WHITE_THRESHOLD = 245;

function loadRasterTile(
  url: string,
  tintColor: [number, number, number],
  targetOpacity: number
): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.width;
      canvas.height = image.height;

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("Unable to acquire 2D canvas context"));
        return;
      }

      ctx.drawImage(image, 0, 0);

      try {
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const { data } = imageData;
        let modified = false;

        for (let i = 0; i < data.length; i += 4) {
          const originalAlpha = data[i + 3];
          if (originalAlpha === 0) {
            continue;
          }

          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];
          const minChannel = Math.min(r, g, b);
          const maxChannel = Math.max(r, g, b);

          if (minChannel >= WHITE_THRESHOLD && maxChannel >= WHITE_THRESHOLD) {
            data[i + 3] = 0;
            modified = true;
            continue;
          }

          // Keep only the hazard pixels and recolor them.
          data[i] = tintColor[0];
          data[i + 1] = tintColor[1];
          data[i + 2] = tintColor[2];
          const targetAlpha = Math.round(targetOpacity * 255);
          data[i + 3] = Math.min(targetAlpha, originalAlpha);
          modified = true;
        }

        if (modified) {
          ctx.putImageData(imageData, 0, 0);
        }
      } catch (processingError) {
        console.warn("Failed to post-process SLOSH tile", processingError);
      }

      resolve(canvas);
    };
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

            const tintColor = SLOSH_CATEGORY_COLORS[category] ?? [255, 255, 255];

            const url = TILE_URL.replace("{category}", category)
              .replace("{z}", String(z))
              .replace("{x}", String(x))
              .replace("{y}", String(y));

            console.info(`Loading SLOSH tile: ${url}`);

            const targetAlpha = SLOSH_CATEGORY_ALPHA[category] ?? 0.7;

            return loadRasterTile(url, tintColor, targetAlpha);
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

            return new BitmapLayer(props, {
              image: data,
              bounds,
              data: null,
              opacity: 0.65,
              transparentColor: [0, 0, 0, 0]
            });
          }
        })
    );
  }, [enabledCategories]);

  useEffect(() => {
    if (!overlay) return;
    overlay.setProps({ layers });
    if (typeof overlay.requestRedraw === "function") {
      overlay.requestRedraw();
    } else if ((overlay as unknown as { _deck?: { setNeedsRedraw?: (reason: string) => void } })._deck?.setNeedsRedraw) {
      (overlay as unknown as { _deck?: { setNeedsRedraw?: (reason: string) => void } })._deck?.setNeedsRedraw?.("slosh-overlay-update");
    }
  }, [overlay, layers]);

  return null;
}
