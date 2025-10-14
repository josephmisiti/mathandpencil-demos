const authUrl = (import.meta.env.VITE_EAGLEVIEW_AUTH_URL || "").trim();
const apiToken = (import.meta.env.VITE_ACORD_API_TOKEN || "").trim();

export type ImageDirection = "ortho" | "north" | "east" | "south" | "west";

export type ImageResource = {
  urn: string;
  tilebox: {
    z: number;
    top: number;
    bottom: number;
    left: number;
    right: number;
  };
  zoom_range: {
    minimum_zoom_level: number;
    maximum_zoom_level: number;
  };
};

export type DiscoveryResult = {
  ortho: ImageResource | null;
  north: ImageResource | null;
  east: ImageResource | null;
  south: ImageResource | null;
  west: ImageResource | null;
};

export const discoverImagesForLocation = async (
  lat: number,
  lng: number
): Promise<DiscoveryResult | null> => {
  if (!authUrl || !apiToken) {
    console.error("EagleView auth URL or API token not configured");
    return null;
  }

  try {
    const sanitizedUrl = authUrl.endsWith("/") ? authUrl.slice(0, -1) : authUrl;
    const url = `${sanitizedUrl}/api/v1/eagleview/discovery`;

    console.log("Discovering images for location via backend proxy", { lat, lng, url });

    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ lat, lng }),
    });

    if (!response.ok) {
      console.error("Discovery API error:", response.status, await response.text());
      return null;
    }

    const data = await response.json();
    console.log("Discovery result:", data);

    if (!data.captures || data.captures.length === 0) {
      console.warn("No captures found for location");
      return null;
    }

    const firstCapture = data.captures[0];
    const result: DiscoveryResult = {
      ortho: null,
      north: null,
      east: null,
      south: null,
      west: null,
    };

    // Extract ortho
    if (firstCapture.orthos?.images?.[0]) {
      const orthoImage = firstCapture.orthos.images[0];
      result.ortho = {
        urn: orthoImage.urn,
        tilebox: orthoImage.resources.tilebox,
        zoom_range: orthoImage.zoom_range,
      };
    }

    // Extract obliques
    for (const direction of ["north", "east", "south", "west"] as const) {
      const oblique = firstCapture.obliques?.[direction];
      if (oblique?.images?.[0]) {
        const image = oblique.images[0];
        result[direction] = {
          urn: image.urn,
          tilebox: image.resources.tilebox,
          zoom_range: image.zoom_range,
        };
      }
    }

    return result;
  } catch (error) {
    console.error("Error discovering images:", error);
    return null;
  }
};
