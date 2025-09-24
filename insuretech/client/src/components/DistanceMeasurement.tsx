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

      // Show distance label when distance is calculated
      if (distance && distance > 0) {
        const midpoint = getMidpoint(points[0], points[1]);

        // Convert to different units
        const feet = distance * 3.28084; // 1 meter = 3.28084 feet
        const miles = distance * 0.000621371; // 1 meter = 0.000621371 miles

        let content = '';
        if (distance < 1000) {
          // Show meters and feet for shorter distances
          content = `
            <div style="
              background: white;
              border: 1px solid #4285F4;
              border-radius: 6px;
              padding: 8px 12px;
              box-shadow: 0 2px 8px rgba(0,0,0,0.15);
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
              font-size: 13px;
              line-height: 1.4;
              text-align: center;
              min-width: 120px;
            ">
              <div style="font-weight: 600; color: #4285F4; margin-bottom: 4px;">Distance</div>
              <div style="color: #333;">
                <div>${distance.toFixed(1)} m</div>
                <div>${feet.toFixed(1)} ft</div>
              </div>
              ${onClear ? '<button onclick="window.clearDistanceMeasurement()" style="margin-top: 6px; padding: 2px 6px; font-size: 11px; color: #666; background: none; border: 1px solid #ddd; border-radius: 3px; cursor: pointer;">Clear</button>' : ''}
            </div>
          `;
        } else {
          // Show kilometers and miles for longer distances
          const kilometers = distance / 1000;
          content = `
            <div style="
              background: white;
              border: 1px solid #4285F4;
              border-radius: 6px;
              padding: 8px 12px;
              box-shadow: 0 2px 8px rgba(0,0,0,0.15);
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
              font-size: 13px;
              line-height: 1.4;
              text-align: center;
              min-width: 120px;
            ">
              <div style="font-weight: 600; color: #4285F4; margin-bottom: 4px;">Distance</div>
              <div style="color: #333;">
                <div>${kilometers.toFixed(2)} km</div>
                <div>${miles.toFixed(2)} mi</div>
              </div>
              ${onClear ? '<button onclick="window.clearDistanceMeasurement()" style="margin-top: 6px; padding: 2px 6px; font-size: 11px; color: #666; background: none; border: 1px solid #ddd; border-radius: 3px; cursor: pointer;">Clear</button>' : ''}
            </div>
          `;
        }

        const infoWindow = new google.maps.InfoWindow({
          content: content,
          position: midpoint,
          disableAutoPan: true,
          headerDisabled: true,
          pixelOffset: new google.maps.Size(0, -10),
        });

        infoWindow.open(map);
        distanceLabelRef.current = infoWindow;
      }
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