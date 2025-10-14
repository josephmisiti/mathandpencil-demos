import { useState, useEffect, useRef } from "react";
import { APIProvider } from "@vis.gl/react-google-maps";
import { SignedIn, SignedOut } from "@clerk/clerk-react";
import AddressSearch from "./components/AddressSearch";
import MapView from "./components/MapView";
import Navigation from "./components/Navigation";
import SignInPage from "./components/SignInPage";
import { Location } from "./types/location";

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";

const DEFAULT_CENTER: Location = {
  lat: 41.256537,
  lng: -95.934503,
  address: "Omaha, NE"
};

const DEFAULT_ZOOM = 12;

const App = () => {
  const [mapCenter, setMapCenter] = useState<Location>(DEFAULT_CENTER);
  const [markers, setMarkers] = useState<Location[]>([]);
  const [initialAddress, setInitialAddress] = useState("");
  const [mapZoom, setMapZoom] = useState<number>(DEFAULT_ZOOM);
  const [isRoofAnalysisActive, setIsRoofAnalysisActive] = useState(false);
  const [isConstructionAnalysisActive, setIsConstructionAnalysisActive] =
    useState(false);
  const [mapControlsVisible, setMapControlsVisible] = useState(true);
  const roofPanelContainerRef = useRef<HTMLDivElement | null>(null);
  const constructionPanelContainerRef = useRef<HTMLDivElement | null>(null);

  // Read URL parameters on mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const lat = urlParams.get("lat");
    const lng = urlParams.get("lng");
    const address = urlParams.get("address");
    const zoom = urlParams.get("zoom");

    if (lat && lng) {
      const decodedAddress = address ? decodeURIComponent(address) : "";
      setMapCenter({
        lat: parseFloat(lat),
        lng: parseFloat(lng),
        address: decodedAddress
      });
    }

    if (lat && lng && address) {
      const decodedAddress = decodeURIComponent(address);
      const selectedLocation: Location = {
        lat: parseFloat(lat),
        lng: parseFloat(lng),
        address: decodedAddress
      };
      setMarkers([selectedLocation]);
      setInitialAddress(decodedAddress);
    }

    if (zoom) {
      const parsedZoom = parseFloat(zoom);
      if (!Number.isNaN(parsedZoom)) {
        setMapZoom(parsedZoom);
      }
    }
  }, []);

  const handleLocationSelect = (location: Location) => {
    setMapCenter(location);
    setMarkers([location]);

    // Update URL parameters
    const url = new URL(window.location.href);
    url.searchParams.set("lat", location.lat.toString());
    url.searchParams.set("lng", location.lng.toString());
    url.searchParams.set("address", encodeURIComponent(location.address));
    url.searchParams.set("zoom", mapZoom.toFixed(0));
    window.history.pushState({}, "", url.toString());
  };

  const handleAddressClear = () => {
    setMapCenter(DEFAULT_CENTER);
    setMarkers([]);
    setMapZoom(DEFAULT_ZOOM);

    // Clear URL parameters
    const url = new URL(window.location.href);
    url.searchParams.delete("lat");
    url.searchParams.delete("lng");
    url.searchParams.delete("address");
    url.searchParams.delete("zoom");
    window.history.pushState({}, "", url.toString());
  };

  const handleMapViewChange = (view: {
    center: { lat: number; lng: number };
    zoom: number;
  }) => {
    const { center, zoom } = view;
    setMapCenter((prev) => {
      if (
        Math.abs(prev.lat - center.lat) < 1e-7 &&
        Math.abs(prev.lng - center.lng) < 1e-7
      ) {
        return prev;
      }
      return {
        ...prev,
        lat: center.lat,
        lng: center.lng
      };
    });
    setMapZoom((prev) => (Math.abs(prev - zoom) < 1e-7 ? prev : zoom));

    const url = new URL(window.location.href);
    url.searchParams.set("lat", center.lat.toFixed(6));
    url.searchParams.set("lng", center.lng.toFixed(6));
    url.searchParams.set("zoom", zoom.toFixed(0));
    window.history.replaceState({}, "", url.toString());
  };

  return (
    <>
      <SignedOut>
        <SignInPage />
      </SignedOut>

      <SignedIn>
        <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
          <div className="flex w-screen h-screen">
            <Navigation
              onMenuToggle={() => setMapControlsVisible(!mapControlsVisible)}
              isMenuVisible={mapControlsVisible}
            />

            <div className="relative flex-1">
              <MapView
                center={mapCenter}
                markers={markers}
                zoom={mapZoom}
                onViewChange={handleMapViewChange}
                onRoofAnalysisVisibilityChange={setIsRoofAnalysisActive}
                roofAnalysisPanelRef={roofPanelContainerRef}
                onConstructionAnalysisVisibilityChange={
                  setIsConstructionAnalysisActive
                }
                constructionAnalysisPanelRef={constructionPanelContainerRef}
                mapControlsVisible={mapControlsVisible}
                onMapControlsToggle={() => setMapControlsVisible(!mapControlsVisible)}
              />

              <div className="absolute top-4 left-4 z-10 flex h-[calc(100vh-2rem)] w-96 flex-col gap-4">
                <AddressSearch
                  onLocationSelect={handleLocationSelect}
                  onAddressClear={handleAddressClear}
                  initialAddress={initialAddress}
                  hidePdfUpload={isRoofAnalysisActive || isConstructionAnalysisActive}
                />
                <div
                  ref={roofPanelContainerRef}
                  className={
                    isRoofAnalysisActive
                      ? "flex-1 min-h-0 overflow-y-auto pr-2"
                      : "hidden"
                  }
                />
                <div
                  ref={constructionPanelContainerRef}
                  className={
                    isConstructionAnalysisActive
                      ? "flex-1 min-h-0 overflow-y-auto pr-2"
                      : "hidden"
                  }
                />
              </div>
            </div>
          </div>
        </APIProvider>
      </SignedIn>
    </>
  );
};

export default App;
