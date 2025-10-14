// Parse enabled layers from environment variable
// Format: VITE_ENABLED_LAYERS="highres,floodzone,fema,slosh"
// If not set, all layers are enabled by default

export type LayerType = "highres" | "floodzone" | "fema" | "slosh";

const ENABLED_LAYERS_ENV = import.meta.env.VITE_ENABLED_LAYERS;
// Parse the comma-separated list of enabled layers
const parseEnabledLayers = (): Set<LayerType> | null => {
  if (!ENABLED_LAYERS_ENV) {
    return null; // null means all layers are disabled (default behavior)
  }

  const layers = ENABLED_LAYERS_ENV.split(",")
    .map((layer: string) => layer.trim().toLowerCase())
    .filter((layer: string) => layer.length > 0);

  return new Set(layers as LayerType[]);
};

const enabledLayersSet = parseEnabledLayers();

export const isLayerEnabled = (layer: LayerType): boolean => {
  // If VITE_ENABLED_LAYERS is not set, all layers are disabled
  if (enabledLayersSet === null) {
    return false;
  }

  return enabledLayersSet.has(layer);
};

export const LAYERS_CONFIG = {
  highres: isLayerEnabled("highres"),
  floodzone: isLayerEnabled("floodzone"),
  fema: isLayerEnabled("fema"),
  slosh: isLayerEnabled("slosh")
};
