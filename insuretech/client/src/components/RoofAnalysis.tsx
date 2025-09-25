import React, { useState } from 'react';
import FabricCanvas from './FabricCanvas';
import { fabric } from 'fabric';

const RoofAnalysis: React.FC = () => {
  const [roofObjects, setRoofObjects] = useState<fabric.Object[]>([]);

  const handleObjectAdded = (object: fabric.Object) => {
    setRoofObjects(prevObjects => [...prevObjects, object]);
    console.log('Object added:', object);
    if (object.aCoords) {
      console.log('Bounding box:', object.aCoords);
      const canvas = object.canvas;
      if (canvas) {
        const imageData = canvas.toDataURL({
          format: 'png',
          left: object.left,
          top: object.top,
          width: object.width,
          height: object.height,
        });

        const apiToken = import.meta.env.VITE_API_TOKEN;

        fetch('http://localhost:8000/save-image', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiToken}`,
          },
          body: JSON.stringify({ image_data: imageData }),
        })
          .then(response => response.json())
          .then(data => console.log(data))
          .catch(error => console.error('Error:', error));
      }
    }
  };

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}>
      <FabricCanvas onObjectAdded={handleObjectAdded} />
    </div>
  );
};

export default RoofAnalysis;