import { useEffect, useState } from "react";
import { ImageResource } from "../services/eagleViewDiscovery";

const authUrl = (import.meta.env.VITE_EAGLEVIEW_AUTH_URL || "").trim();
const apiToken = (import.meta.env.VITE_ACORD_API_TOKEN || "").trim();

type ObliqueImageOverlayProps = {
  imageResource: ImageResource;
  map: google.maps.Map;
};

export const ObliqueImageOverlay = ({ imageResource, map }: ObliqueImageOverlayProps) => {
  const [overlay, setOverlay] = useState<google.maps.GroundOverlay | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  useEffect(() => {
    // Fetch the center tile from the tilebox
    const { z, left, top } = imageResource.tilebox;
    const tileUrl = `${authUrl.endsWith("/") ? authUrl.slice(0, -1) : authUrl}/api/v1/eagleview/tiles/${encodeURIComponent(imageResource.urn)}/${z}/${left}/${top}`;

    console.log("ObliqueImageOverlay: Fetching oblique tile", tileUrl);

    fetch(tileUrl, {
      headers: {
        Authorization: `Bearer ${apiToken}`
      }
    })
      .then(response => response.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        setImageUrl(url);
      })
      .catch(error => {
        console.error("ObliqueImageOverlay: Error fetching tile", error);
      });

    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageResource]);

  useEffect(() => {
    if (!imageUrl || !imageResource.ground_footprint) return;

    // Parse ground footprint to get bounds
    const coords = imageResource.ground_footprint.coordinates[0][0];
    const lngs = coords.map(c => c[0]);
    const lats = coords.map(c => c[1]);

    const bounds = new google.maps.LatLngBounds(
      new google.maps.LatLng(Math.min(...lats), Math.min(...lngs)),
      new google.maps.LatLng(Math.max(...lats), Math.max(...lngs))
    );

    console.log("ObliqueImageOverlay: Creating ground overlay", { bounds, imageUrl });

    const groundOverlay = new google.maps.GroundOverlay(imageUrl, bounds, {
      opacity: 0.8,
      clickable: false
    });

    groundOverlay.setMap(map);
    setOverlay(groundOverlay);

    return () => {
      if (overlay) {
        overlay.setMap(null);
      }
    };
  }, [imageUrl, imageResource, map]);

  return null;
};
