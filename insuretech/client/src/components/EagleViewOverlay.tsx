import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { TileLayer } from "@deck.gl/geo-layers";
import { BitmapLayer } from "@deck.gl/layers";
import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";
import { getEagleViewBearerToken } from "../services/eagleViewAuth";
import { ImageResource } from "../services/eagleViewDiscovery";

const baseUrl = (import.meta.env.VITE_APP_EAGLEVIEW_BASE_URL || "").trim();

type EagleViewOverlayProps = {
  enabled: boolean;
  imageResource: ImageResource | null;
};

export const EagleViewOverlay = ({
  enabled,
  imageResource
}: EagleViewOverlayProps) => {
  const map = useMap();
  const [overlay, setOverlay] = useState<GoogleMapsOverlay | null>(null);
  const [bearerToken, setBearerToken] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setBearerToken(null);
      return;
    }

    console.log("EagleViewOverlay: Fetching bearer token");
    getEagleViewBearerToken().then((token) => {
      console.log("EagleViewOverlay: Bearer token received", token);
      if (token) {
        setBearerToken(token);
      }
    });
  }, [enabled]);

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
      imageResource: imageResource ? "present" : "missing",
      bearerToken: bearerToken ? "present" : "missing"
    });

    const layers =
      enabled && bearerToken && imageResource
        ? [
            new TileLayer({
              id: `eagleview-image-${imageResource.urn}`,
              data: (tile: { x: number; y: number; z: number }) => {
                const sanitizedUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
                const encodedUrn = encodeURIComponent(imageResource.urn);
                return `${sanitizedUrl}/imagery/v3/images/${encodedUrn}/tiles/${tile.z}/${tile.x}/${tile.y}?format=IMAGE_FORMAT_PNG`;
              },
              minZoom: imageResource.zoom_range.minimum_zoom_level,
              maxZoom: imageResource.zoom_range.maximum_zoom_level,
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
                    Authorization: `Bearer ${bearerToken}`,
                    Accept: "image/png"
                  },
                  credentials: "omit"
                }
              }
            })
          ]
        : [];

    console.log("EagleViewOverlay: Setting layers", layers.length);
    overlay.setProps({ layers });
  }, [overlay, enabled, imageResource, bearerToken]);

  return null;
};
