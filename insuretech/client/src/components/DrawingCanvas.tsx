import React, { useCallback, useEffect, useRef } from 'react';

interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface DrawingCanvasProps {
  onDrawComplete: (bounds: Bounds) => void;
  disabled?: boolean;
  highlight?: Bounds | null;
}

const MIN_SELECTION_SIZE = 10; // pixels

const DrawingCanvas: React.FC<DrawingCanvasProps> = ({ onDrawComplete, disabled = false, highlight = null }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const isDrawingRef = useRef(false);
  const startPointRef = useRef<{ x: number; y: number } | null>(null);

  const syncCanvasSize = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    const width = Math.round(rect.width * dpr);
    const height = Math.round(rect.height * dpr);

    if (canvas.width !== width || canvas.height !== height) {
      const ctx = canvas.getContext('2d');
      canvas.width = width;
      canvas.height = height;
      if (ctx) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, rect.width, rect.height);
      }
    }
  }, []);

  const clearCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
  }, []);

  const drawBounds = useCallback((bounds: Bounds) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    clearCanvas();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#ef4444';
    ctx.setLineDash([6, 6]);
    ctx.strokeRect(bounds.x, bounds.y, bounds.width, bounds.height);
  }, [clearCanvas]);

  useEffect(() => {
    syncCanvasSize();
    const handleResize = () => {
      syncCanvasSize();
      if (highlight) {
        drawBounds(highlight);
      } else {
        clearCanvas();
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [syncCanvasSize, drawBounds, clearCanvas, highlight]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const getPointerPosition = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };
    };

    const handlePointerDown = (event: PointerEvent) => {
      if (disabled) return;
      event.preventDefault();
      canvas.setPointerCapture(event.pointerId);
      const position = getPointerPosition(event);
      startPointRef.current = position;
      isDrawingRef.current = true;
    };

    const handlePointerMove = (event: PointerEvent) => {
      if (!isDrawingRef.current || !startPointRef.current) return;
      event.preventDefault();
      const position = getPointerPosition(event);
      const { x: startX, y: startY } = startPointRef.current;
      const bounds: Bounds = {
        x: Math.min(startX, position.x),
        y: Math.min(startY, position.y),
        width: Math.abs(position.x - startX),
        height: Math.abs(position.y - startY),
      };
      drawBounds(bounds);
    };

    const handlePointerUp = (event: PointerEvent) => {
      if (!isDrawingRef.current || !startPointRef.current) return;
      event.preventDefault();
      canvas.releasePointerCapture(event.pointerId);
      isDrawingRef.current = false;
      const position = getPointerPosition(event);
      const { x: startX, y: startY } = startPointRef.current;
      const bounds: Bounds = {
        x: Math.min(startX, position.x),
        y: Math.min(startY, position.y),
        width: Math.abs(position.x - startX),
        height: Math.abs(position.y - startY),
      };

      if (bounds.width < MIN_SELECTION_SIZE || bounds.height < MIN_SELECTION_SIZE) {
        clearCanvas();
      } else {
        drawBounds(bounds);
        onDrawComplete(bounds);
      }

      startPointRef.current = null;
    };

    const handlePointerLeave = (event: PointerEvent) => {
      if (!isDrawingRef.current) return;
      event.preventDefault();
      isDrawingRef.current = false;
      startPointRef.current = null;
      clearCanvas();
    };

    canvas.addEventListener('pointerdown', handlePointerDown);
    canvas.addEventListener('pointermove', handlePointerMove);
    canvas.addEventListener('pointerup', handlePointerUp);
    canvas.addEventListener('pointerleave', handlePointerLeave);

    return () => {
      canvas.removeEventListener('pointerdown', handlePointerDown);
      canvas.removeEventListener('pointermove', handlePointerMove);
      canvas.removeEventListener('pointerup', handlePointerUp);
      canvas.removeEventListener('pointerleave', handlePointerLeave);
    };
  }, [drawBounds, clearCanvas, onDrawComplete, disabled]);

  useEffect(() => {
    if (!highlight) {
      clearCanvas();
    } else {
      drawBounds(highlight);
    }
  }, [highlight, drawBounds, clearCanvas]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 30,
        cursor: disabled ? 'not-allowed' : 'crosshair',
      }}
    />
  );
};

export default DrawingCanvas;
