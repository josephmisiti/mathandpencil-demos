import { useEffect, useMemo, useRef, useState } from 'react';
import type { Location } from '../types/location';
import {
  EagleViewImagery,
  fetchEagleViewImagery
} from '../services/eagleView';

type ImageryStatus = 'idle' | 'loading' | 'ready' | 'error';

type UseEagleViewImageryResult = {
  imagery: EagleViewImagery | null;
  status: ImageryStatus;
  error: string | null;
};

const roundCoordinate = (value: number) => Number(value.toFixed(6));

export const useEagleViewImagery = (
  enabled: boolean,
  location: Location | null
): UseEagleViewImageryResult => {
  const cacheRef = useRef(new Map<string, EagleViewImagery>());
  const [status, setStatus] = useState<ImageryStatus>('idle');
  const [imagery, setImagery] = useState<EagleViewImagery | null>(null);
  const [error, setError] = useState<string | null>(null);

  const lookupKey = useMemo(() => {
    if (!location) return null;
    const lat = roundCoordinate(location.lat);
    const lng = roundCoordinate(location.lng);
    return `${lat},${lng}`;
  }, [location?.lat, location?.lng]);

  useEffect(() => {
    if (!enabled || !location || !lookupKey) {
      setStatus('idle');
      setImagery(null);
      setError(null);
      return;
    }

    if (cacheRef.current.has(lookupKey)) {
      setImagery(cacheRef.current.get(lookupKey) ?? null);
      setStatus('ready');
      setError(null);
      return;
    }

    const controller = new AbortController();
    setStatus('loading');
    setError(null);
    setImagery(null);

    fetchEagleViewImagery(location, controller.signal)
      .then(result => {
        if (!result) {
          setStatus('error');
          setError('No EagleView imagery available for this location.');
          setImagery(null);
          return;
        }

        cacheRef.current.set(lookupKey, result);
        setImagery(result);
        setStatus('ready');
      })
      .catch(err => {
        if (controller.signal.aborted) return;
        setStatus('error');
        setError(err instanceof Error ? err.message : 'Failed to load EagleView imagery');
      });

    return () => controller.abort();
  }, [enabled, location, lookupKey]);

  return useMemo(() => ({imagery, status, error}), [error, imagery, status]);
};
