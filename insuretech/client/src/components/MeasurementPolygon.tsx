import { useEffect, useRef } from "react";
import { useMap } from "@vis.gl/react-google-maps";

interface MeasurementPolygonProps {
  points: google.maps.LatLngLiteral[];
  area?: number; // in square meters
}

export default function MeasurementPolygon({ points, area }: MeasurementPolygonProps) {
  const map = useMap();
  const polygonRef = useRef<google.maps.Polygon | null>(null);
  const polylineRef = useRef<google.maps.Polyline | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const areaLabelRef = useRef<google.maps.InfoWindow | null>(null);

  // Calculate polygon centroid for label placement
  const getPolygonCenter = (points: google.maps.LatLngLiteral[]): google.maps.LatLngLiteral => {
    let totalLat = 0;
    let totalLng = 0;
    points.forEach(point => {
      totalLat += point.lat;
      totalLng += point.lng;
    });
    return {
      lat: totalLat / points.length,
      lng: totalLng / points.length
    };
  };

  useEffect(() => {
    if (!map) return;

    // Clean up existing elements
    if (polygonRef.current) {
      polygonRef.current.setMap(null);
      polygonRef.current = null;
    }
    if (polylineRef.current) {
      polylineRef.current.setMap(null);
      polylineRef.current = null;
    }
    if (areaLabelRef.current) {
      areaLabelRef.current.close();
      areaLabelRef.current = null;
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
          fillColor: "#FF6B6B",
          fillOpacity: 1,
          strokeColor: "#FFFFFF",
          strokeWeight: 2,
          scale: 6,
        },
        title: `Point ${index + 1}`,
        clickable: false,
      });

      markersRef.current.push(marker);
    });

    // Show polyline for 2+ points (connecting lines)
    if (points.length >= 2) {
      const polyline = new google.maps.Polyline({
        path: points,
        strokeColor: "#FF6B6B",
        strokeOpacity: 0.8,
        strokeWeight: 2,
        clickable: false,
      });

      polyline.setMap(map);
      polylineRef.current = polyline;
    }

    // Show filled polygon for 3+ points
    if (points.length >= 3) {
      const polygon = new google.maps.Polygon({
        paths: points,
        strokeColor: "#FF6B6B",
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: "#FF6B6B",
        fillOpacity: 0.3,
        clickable: false,
      });

      polygon.setMap(map);
      polygonRef.current = polygon;
    }

    // Area label is now displayed in the top-center panel instead of on the map
  }, [map, points, area]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (polygonRef.current) {
        polygonRef.current.setMap(null);
      }
      if (polylineRef.current) {
        polylineRef.current.setMap(null);
      }
      if (areaLabelRef.current) {
        areaLabelRef.current.close();
      }
      markersRef.current.forEach(marker => marker.setMap(null));
    };
  }, []);

  return null; // This component doesn't render anything directly
}