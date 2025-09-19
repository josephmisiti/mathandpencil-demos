import type { Location } from "../types/location";

export type EagleViewImagery = {
  imageUrn: string;
  tileUrlTemplate: string;
  minZoom?: number;
  maxZoom?: number;
};

const DEFAULT_BASE_URL = "https://sandbox.apis.eagleview.com";

const baseUrl =
  import.meta.env.VITE_EAGLE_VIEW_BASE_URL?.replace(/\/$/, "") ||
  DEFAULT_BASE_URL;
const apiKey = (import.meta.env.VITE_EAGLE_VIEW_API_KEY || "").trim();
const explicitTemplate = import.meta.env.VITE_EAGLE_VIEW_TILE_URL_TEMPLATE;
const discoveryHeaders: Record<string, string> = {
  "Content-Type": "application/json",
  Accept: "application/json"
};

if (apiKey) {
  discoveryHeaders["x-api-key"] = apiKey;
}

const deepSearchForTileTemplate = (
  value: unknown,
  visited: Set<unknown> = new Set()
): string | null => {
  if (!value || typeof value !== "object") return null;
  if (visited.has(value)) return null;
  visited.add(value);

  const container = value as Record<string, unknown>;

  for (const key of Object.keys(container)) {
    const child = container[key];
    if (typeof child === "string") {
      if (
        child.includes("{z}") &&
        child.includes("{x}") &&
        child.includes("{y}")
      ) {
        return child;
      }
    } else if (typeof child === "object" && child !== null) {
      const nested = deepSearchForTileTemplate(child, visited);
      if (nested) return nested;
    }
  }

  return null;
};

const extractNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

const extractZoomRange = (
  capture: Record<string, unknown>
): {
  minZoom?: number;
  maxZoom?: number;
} => {
  const zoomRange =
    capture.zoom_range ?? capture.zoomRange ?? capture.calculated_zoom_range;
  if (!zoomRange || typeof zoomRange !== "object") return {};
  const range = zoomRange as Record<string, unknown>;
  const minZoom =
    extractNumber(
      range.min_zoom ?? range.minZoom ?? range.minimum_zoom ?? range.minimumZoom
    ) ?? undefined;
  const maxZoom =
    extractNumber(
      range.max_zoom ?? range.maxZoom ?? range.maximum_zoom ?? range.maximumZoom
    ) ?? undefined;

  return {
    minZoom,
    maxZoom
  };
};

const extractImageUrn = (
  capture: Record<string, unknown>
): string | undefined => {
  const directUrn = capture.image_urn ?? capture.imageUrn ?? capture.urn;
  if (typeof directUrn === "string" && directUrn.length > 0) return directUrn;

  const image = capture.image;
  if (typeof image === "object" && image && "urn" in image) {
    const urn = (image as Record<string, unknown>).urn;
    if (typeof urn === "string" && urn.length > 0) {
      return urn;
    }
  }

  const images = capture.images;
  if (Array.isArray(images)) {
    for (const entry of images) {
      if (typeof entry === "object" && entry) {
        const urn = extractImageUrn(entry as Record<string, unknown>);
        if (urn) return urn;
      }
    }
  }

  const views = capture.views;
  if (Array.isArray(views)) {
    for (const view of views) {
      if (typeof view === "object" && view) {
        const urn = extractImageUrn(view as Record<string, unknown>);
        if (urn) return urn;
      }
    }
  }

  return undefined;
};

const tryBuildImageryFromCapture = (
  capture: Record<string, unknown>
): EagleViewImagery | null => {
  const tileTemplate = deepSearchForTileTemplate(
    capture.image_resources ?? capture
  );
  const imageUrn = extractImageUrn(capture);

  if (!tileTemplate || !imageUrn) {
    return null;
  }

  const { minZoom, maxZoom } = extractZoomRange(capture);

  return {
    imageUrn,
    tileUrlTemplate: tileTemplate,
    minZoom,
    maxZoom
  };
};

const discoveryRequestBody = (location: Location) => ({
  polygon: {
    geojson: {
      type: "Point",
      coordinates: [location.lng, location.lat]
    }
  },
  view: {
    orthos: {},
    max_images_per_view: 1
  },
  response_props: {
    zoom_range: true,
    image_resources: {}
  }
});

export async function fetchEagleViewImagery(
  location: Location,
  signal?: AbortSignal
): Promise<EagleViewImagery | null> {
  if (explicitTemplate) {
    return {
      imageUrn: "custom-template",
      tileUrlTemplate: explicitTemplate
    };
  }

  if (!apiKey) {
    console.warn(
      "EagleView API key missing; high-resolution imagery disabled."
    );
    return null;
  }

  const requestBody = discoveryRequestBody(location);

  const response = await fetch(
    `${baseUrl}/imagery/v3/discovery/rank/location`,
    {
      method: "POST",
      headers: discoveryHeaders,
      body: JSON.stringify(requestBody),
      signal
    }
  );

  if (!response.ok) {
    throw new Error(
      `EagleView discovery failed (${response.status}): ${response.statusText}`
    );
  }

  const payload = (await response.json()) as Record<string, unknown>;
  const captures = Array.isArray(payload.captures) ? payload.captures : [];

  for (const entry of captures) {
    if (typeof entry !== "object" || !entry) continue;
    const imagery = tryBuildImageryFromCapture(
      entry as Record<string, unknown>
    );
    if (imagery) return imagery;

    const views = (entry as Record<string, unknown>).views;
    if (Array.isArray(views)) {
      for (const view of views) {
        if (typeof view !== "object" || !view) continue;
        const nested = tryBuildImageryFromCapture(
          view as Record<string, unknown>
        );
        if (nested) return nested;
      }
    }
  }

  return null;
}

export const buildTileUrl = (
  template: string,
  imageUrn: string,
  z: number,
  x: number,
  y: number
) => {
  const resolved = template
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
