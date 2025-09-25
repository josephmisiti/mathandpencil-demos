import React, { useEffect, useRef } from 'react';
import { fabric } from 'fabric';

interface FabricCanvasProps {
  onObjectAdded: (object: fabric.Object) => void;
  drawingMode: boolean;
}

const FabricCanvas: React.FC<FabricCanvasProps> = ({ onObjectAdded, drawingMode }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fabricCanvasRef = useRef<fabric.Canvas | null>(null);
  const isDrawing = useRef(false);
  const startPoint = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = new fabric.Canvas(canvasRef.current, {
      selection: false,
      backgroundColor: 'transparent',
    });

    fabricCanvasRef.current = canvas;

    const handleMouseDown = (o: fabric.IEvent) => {
      if (!drawingMode) return;
      isDrawing.current = true;
      const pointer = canvas.getPointer(o.e);
      startPoint.current = { x: pointer.x, y: pointer.y };
    };

    const handleMouseMove = (o: fabric.IEvent) => {
      if (!drawingMode || !isDrawing.current) return;
      const pointer = canvas.getPointer(o.e);
      // You can add logic here to draw a rectangle as the mouse moves
    };

    const handleMouseUp = (o: fabric.IEvent) => {
      if (!drawingMode || !isDrawing.current) return;
      isDrawing.current = false;
      const pointer = canvas.getPointer(o.e);
      const endPoint = { x: pointer.x, y: pointer.y };
      const rect = new fabric.Rect({
        left: startPoint.current!.x,
        top: startPoint.current!.y,
        width: endPoint.x - startPoint.current!.x,
        height: endPoint.y - startPoint.current!.y,
        fill: 'transparent',
        stroke: '#ff0000',
        strokeWidth: 2,
      });
      canvas.add(rect);
      onObjectAdded(rect);
    };

    canvas.on('mouse:down', handleMouseDown);
    canvas.on('mouse:move', handleMouseMove);
    canvas.on('mouse:up', handleMouseUp);

    return () => {
      canvas.off('mouse:down', handleMouseDown);
      canvas.off('mouse:move', handleMouseMove);
      canvas.off('mouse:up', handleMouseUp);
      canvas.dispose();
    };
  }, [drawingMode, onObjectAdded]);

  return <canvas ref={canvasRef} style={{ position: 'absolute', top: 0, left: 0 }} />;
};

export default FabricCanvas;
