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

    // Show area label when area is calculated and polygon exists
    if (area && points.length >= 3) {
      const center = getPolygonCenter(points);

      // Convert to different units
      const squareFeet = area * 10.764; // 1 m² = 10.764 ft²
      const acres = area * 0.000247105; // 1 m² = 0.000247105 acres

      const content = `
        <div style="
          background: white;
          border: 1px solid #ccc;
          border-radius: 6px;
          padding: 8px 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 13px;
          line-height: 1.4;
          text-align: center;
          min-width: 140px;
        ">
          <div style="font-weight: 600; color: #333; margin-bottom: 4px;">Area</div>
          <div style="color: #666;">
            <div>${area.toLocaleString()} m²</div>
            <div>${squareFeet.toLocaleString()} ft²</div>
          </div>
        </div>
      `;

      const infoWindow = new google.maps.InfoWindow({
        content: content,
        position: center,
        disableAutoPan: true,
        headerDisabled: true,
        pixelOffset: new google.maps.Size(0, 0),
      });

      infoWindow.open(map);
      areaLabelRef.current = infoWindow;
    }
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