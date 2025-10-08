import { TileLayer } from "@deck.gl/geo-layers";
import { BitmapLayer } from "@deck.gl/layers";
import type { EagleViewImagery } from "../services/eagleView";

const apiKey = (import.meta.env.VITE_EAGLE_VIEW_API_KEY || "").trim();

type EagleViewLayerProps = {
  id: string;
  imagery: EagleViewImagery;
  visible: boolean;
};

export function EagleViewOverlay({ id, imagery, visible }: EagleViewLayerProps) {
  const { tileUrlTemplate, minZoom, maxZoom, imageUrn } = imagery;

  const buildTileUrl = (z: number, x: number, y: number) => {
    const resolved = tileUrlTemplate
      .replace("{image_urn}", imageUrn)
      .replace("{imageUrn}", imageUrn)
      .replace("{z}", z.toString())
      .replace("{x}", x.toString())
      .replace("{y}", y.toString());

    if (!apiKey) return resolved;

    try {
      const url = new URL(resolved);
      const hasKeyParam = Array.from(url.searchParams.keys()).some(key => {
        const normalized = key.toLowerCase();
        return normalized === "apikey" || normalized === "api_key" || normalized === "x-api-key";
      });

      if (!hasKeyParam) {
        url.searchParams.set("apiKey", apiKey);
      }

      return url.toString();
    } catch (err) {
      const separator = resolved.includes("?") ? "&" : "?";
      return `${resolved}${separator}apiKey=${encodeURIComponent(apiKey)}`;
    }
  };

  const dataUrl = buildTileUrl("{z}", "{x}", "{y}");

  return new TileLayer({
    id,
    data: dataUrl,
    minZoom: minZoom ?? 15,
    maxZoom: maxZoom ?? 22,
    tileSize: 256,
    visible,
    refinementStrategy: "best-available",
    renderSubLayers: (props: any) => {
      const {
        bbox: { west, south, east, north }
      } = props.tile;

      return new BitmapLayer({
        id: `${props.id}-bitmap`,
        image: props.data,
        bounds: [west, south, east, north],
        desaturate: 0,
        opacity: 1,
        transparentColor: [0, 0, 0, 0],
        tintColor: [255, 255, 255]
      });
    },
    loadOptions: {
      fetch: {
        headers: {
          Accept: `image/jpeg`
        }
      }
    }
  });
}