import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { TileLayer } from "@deck.gl/geo-layers";
import { BitmapLayer } from "@deck.gl/layers";
import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";

const DEFAULT_EAGLEVIEW_LAYER_ID = "LatestBestResolution";
const DEFAULT_EAGLEVIEW_STYLE = "default";
const DEFAULT_EAGLEVIEW_TILE_MATRIX_SET = "GoogleMapsCompatible_9-23";
const DEFAULT_EAGLEVIEW_FORMAT = "jpeg";

const baseUrl = (import.meta.env.VITE_APP_EAGLEVIEW_BASE_URL || "").trim();
const apiKey = (import.meta.env.VITE_APP_EAGLEVIEW_API_KEY || "").trim();

type EagleViewOverlayProps = {
  enabled: boolean;
  layerName?: string;
  wmtsStyle?: string;
  wmtsTileMatrixSet?: string;
  imageFormat?: string;
  minZoom?: number;
  maxZoom?: number;
};

console.info("apiKey:", apiKey);

const getZoomBoundsFromTileMatrixSet = (tileMatrixSet: string) => {
  if (tileMatrixSet.startsWith("GoogleMapsCompatible")) {
    return { minZoom: 0, maxZoom: 22 };
  }
  return { minZoom: 15, maxZoom: 22 };
};

export const EagleViewOverlay = ({
  enabled,
  layerName,
  wmtsStyle,
  wmtsTileMatrixSet,
  imageFormat,
  minZoom,
  maxZoom
}: EagleViewOverlayProps) => {
  const map = useMap();
  const [overlay, setOverlay] = useState<GoogleMapsOverlay | null>(null);

  const resolvedLayerId = layerName ?? DEFAULT_EAGLEVIEW_LAYER_ID;
  const resolvedStyle = wmtsStyle ?? DEFAULT_EAGLEVIEW_STYLE;
  const resolvedTileMatrixSet =
    wmtsTileMatrixSet ?? DEFAULT_EAGLEVIEW_TILE_MATRIX_SET;
  const resolvedFormat = imageFormat ?? DEFAULT_EAGLEVIEW_FORMAT;
  const zoomBounds = getZoomBoundsFromTileMatrixSet(resolvedTileMatrixSet);
  const resolvedMinZoom = minZoom ?? zoomBounds.minZoom;
  const resolvedMaxZoom = maxZoom ?? zoomBounds.maxZoom;

  const sanitizedUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;

  const tileBaseUrl = `${sanitizedUrl}/imagery/wmts/v1/visual/tile/${resolvedLayerId}/${resolvedStyle}/${resolvedTileMatrixSet}/{z}/{x}/{y}.${resolvedFormat}`;
  const dataUrl = apiKey
    ? `${tileBaseUrl}${
        tileBaseUrl.includes("?") ? "&" : "?"
      }api_key=${encodeURIComponent(apiKey)}`
    : tileBaseUrl;

  useEffect(() => {
    if (!map) return;

    console.log("EagleViewOverlay: Creating GoogleMapsOverlay");
    const instance = new GoogleMapsOverlay({ layers: [] });
    instance.setMap(map);
    setOverlay(instance);

    return () => {
      console.log("EagleViewOverlay: Cleaning up GoogleMapsOverlay");
      instance.setMap(null);
    };
  }, [map]);

  useEffect(() => {
    if (!overlay) return;

    console.log("EagleViewOverlay: Updating layers", {
      enabled,
      dataUrl,
      minZoom: resolvedMinZoom,
      maxZoom: resolvedMaxZoom
    });

    const layers = enabled
      ? [
          new TileLayer({
            id: `eagleview-${resolvedLayerId}-layer`,
            data: dataUrl,
            minZoom: resolvedMinZoom,
            maxZoom: resolvedMaxZoom,
            tileSize: 256,
            maxCacheSize: 40,
            refinementStrategy: "best-available",
            renderSubLayers: (props) => {
              const {
                // @ts-ignore
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
                method: "GET",
                headers: {
                  Accept: `image/${resolvedFormat}`
                },
                credentials: "omit"
              }
            }
          })
        ]
      : [];

    console.log("EagleViewOverlay: Setting layers", layers.length);
    overlay.setProps({ layers });
  }, [
    overlay,
    enabled,
    dataUrl,
    resolvedLayerId,
    resolvedMinZoom,
    resolvedMaxZoom,
    resolvedFormat
  ]);

  return null;
};
