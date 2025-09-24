import { useEffect, useRef } from "react";
import { useMap } from "@vis.gl/react-google-maps";

interface DistanceMeasurementProps {
  points: google.maps.LatLngLiteral[];
  distance?: number; // in meters
  onClear?: () => void; // Callback to clear the measurement
}

export default function DistanceMeasurement({ points, distance, onClear }: DistanceMeasurementProps) {
  const map = useMap();
  const polylineRef = useRef<google.maps.Polyline | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const distanceLabelRef = useRef<google.maps.InfoWindow | null>(null);

  // Calculate midpoint for label placement
  const getMidpoint = (point1: google.maps.LatLngLiteral, point2: google.maps.LatLngLiteral): google.maps.LatLngLiteral => {
    return {
      lat: (point1.lat + point2.lat) / 2,
      lng: (point1.lng + point2.lng) / 2
    };
  };

  useEffect(() => {
    if (!map) return;

    // Set up global callback for clearing measurement
    if (onClear) {
      (window as any).clearDistanceMeasurement = onClear;
    }

    // Clean up existing elements
    if (polylineRef.current) {
      polylineRef.current.setMap(null);
      polylineRef.current = null;
    }
    if (distanceLabelRef.current) {
      distanceLabelRef.current.close();
      distanceLabelRef.current = null;
    }
    markersRef.current.forEach(marker => marker.setMap(null));
    markersRef.current = [];

    if (points.length === 0) return;

    // Create markers for each point
    points.forEach((point, index) => {
      const marker = new google.maps.Marker({
        position: point,
        map: map,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          fillColor: "#4285F4",
          fillOpacity: 1,
          strokeColor: "#FFFFFF",
          strokeWeight: 2,
          scale: 7,
        },
        title: `Point ${index + 1}`,
        clickable: false,
      });

      markersRef.current.push(marker);
    });

    // Show line for 2 points
    if (points.length === 2) {
      const polyline = new google.maps.Polyline({
        path: points,
        strokeColor: "#4285F4",
        strokeOpacity: 1,
        strokeWeight: 3,
        clickable: false,
      });

      polyline.setMap(map);
      polylineRef.current = polyline;

      // Distance label is now displayed in the top-center panel instead of on the map
    }
  }, [map, points, distance]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (polylineRef.current) {
        polylineRef.current.setMap(null);
      }
      if (distanceLabelRef.current) {
        distanceLabelRef.current.close();
      }
      markersRef.current.forEach(marker => marker.setMap(null));
    };
  }, []);

  return null; // This component doesn't render anything directly
}