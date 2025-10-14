import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { TileLayer } from "@deck.gl/geo-layers";
import { BitmapLayer } from "@deck.gl/layers";
import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";
import { ImageResource } from "../services/eagleViewDiscovery";
import { ObliqueImageOverlay } from "./ObliqueImageOverlay";

const authUrl = (import.meta.env.VITE_EAGLEVIEW_AUTH_URL || "").trim();
const apiToken = (import.meta.env.VITE_ACORD_API_TOKEN || "").trim();

type EagleViewOverlayProps = {
  enabled: boolean;
  imageResource: ImageResource | null;
  bearerToken: string | null;
};

export const EagleViewOverlay = ({
  enabled,
  imageResource,
  bearerToken
}: EagleViewOverlayProps) => {
  const map = useMap();
  const [overlay, setOverlay] = useState<GoogleMapsOverlay | null>(null);
  const [previousLayerCount, setPreviousLayerCount] = useState(0);

  // Determine if this is an oblique image (must check before any hooks)
  const isOblique = enabled && imageResource?.type === "oblique";

  useEffect(() => {
    if (!map) {
      return;
    }

    let instance: GoogleMapsOverlay | null = null;
    try {
      instance = new GoogleMapsOverlay({ layers: [] });
      instance.setMap(map);
      setOverlay(instance);
    } catch (error) {
      console.error(
        "EagleViewOverlay: Error creating GoogleMapsOverlay",
        error
      );
    }

    return () => {
      if (instance) {
        instance.setMap(null);
      }
    };
  }, [map]);

  useEffect(() => {
    if (!overlay) return;

    const mapZoom = map?.getZoom?.() || 0;

    console.log("EagleViewOverlay: Updating layers", {
      enabled,
      imageResource: imageResource
        ? {
            urn: imageResource.urn,
            minZoom: imageResource.zoom_range.minimum_zoom_level,
            maxZoom: imageResource.zoom_range.maximum_zoom_level
          }
        : "missing",
      bearerToken: bearerToken ? "present" : "missing",
      authUrl,
      currentMapZoom: mapZoom
    });

    if (
      imageResource &&
      mapZoom < imageResource.zoom_range.minimum_zoom_level
    ) {
      console.warn(
        `EagleViewOverlay: Current map zoom (${mapZoom}) is below minimum zoom (${imageResource.zoom_range.minimum_zoom_level}). Tiles will not be visible. Zoom in to see imagery.`
      );
    }

    if (
      imageResource &&
      mapZoom > imageResource.zoom_range.maximum_zoom_level
    ) {
      console.warn(
        `EagleViewOverlay: Current map zoom (${mapZoom}) is above maximum zoom (${imageResource.zoom_range.maximum_zoom_level}). Tiles will not be visible. Zoom out to see imagery. (Oblique images typically require zoom 5-8 or lower)`
      );
    }

    const layers =
      enabled && bearerToken && imageResource
        ? [
            new TileLayer({
              id: `eagleview-image-${imageResource.urn}`,
              visible: true,
              opacity: 1,
              data: `${
                authUrl.endsWith("/") ? authUrl.slice(0, -1) : authUrl
              }/api/v1/eagleview/tiles/${encodeURIComponent(
                imageResource.urn
              )}/{z}/{x}/{y}`,
              minZoom: imageResource.zoom_range.minimum_zoom_level,
              maxZoom: imageResource.zoom_range.maximum_zoom_level,
              tileSize: 256,
              maxCacheSize: 100,
              maxRequests: 10,
              refinementStrategy: "no-overlap",
              onTileLoad: (tile: any) => {
                console.log("EagleViewOverlay: Tile loaded successfully", tile);
              },
              onTileError: (error: any, tile: any) => {
                console.error("EagleViewOverlay: Tile load error", error, tile);
              },
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
                  headers: {
                    Authorization: `Bearer ${apiToken}`
                  }
                }
              }
            })
          ]
        : [];

    console.log(
      "EagleViewOverlay: Setting layers",
      layers.length,
      layers.length > 0 ? "layer created" : "no layers"
    );
    if (layers.length > 0) {
      console.log("EagleViewOverlay: Layer config:", {
        id: layers[0].id,
        minZoom: layers[0].props.minZoom,
        maxZoom: layers[0].props.maxZoom,
        visible: layers[0].props.visible,
        opacity: layers[0].props.opacity
      });
    }
    overlay.setProps({ layers });

    if (layers.length > previousLayerCount && layers.length > 0 && map) {
      console.log("EagleViewOverlay: Forcing map redraw - layer added");
      requestAnimationFrame(() => {
        map.setCenter(map.getCenter()!);
      });
    }
    setPreviousLayerCount(layers.length);
  }, [overlay, enabled, imageResource, bearerToken, map, previousLayerCount]);

  // Use ObliqueImageOverlay for oblique images
  if (isOblique && map && imageResource) {
    return <ObliqueImageOverlay imageResource={imageResource} map={map} />;
  }

  return null;
};
