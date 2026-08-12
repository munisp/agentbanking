import { useState, useEffect, useCallback } from 'react';

interface RealTimeDataOptions {
  interval?: number; // Update interval in milliseconds
  enabled?: boolean; // Whether to enable real-time updates
}

/**
 * Hook for simulating real-time data updates
 * Provides animated data changes for demo purposes
 */
export function useRealTimeData<T>(
  initialData: T,
  updateFn: (currentData: T) => T,
  options: RealTimeDataOptions = {}
) {
  const { interval = 5000, enabled = true } = options;
  const [data, setData] = useState<T>(initialData);
  const [isLive, setIsLive] = useState(enabled);

  const update = useCallback(() => {
    setData((current) => updateFn(current));
  }, [updateFn]);

  useEffect(() => {
    if (!isLive) return;

    const timer = setInterval(update, interval);
    return () => clearInterval(timer);
  }, [isLive, interval, update]);

  const toggleLive = useCallback(() => {
    setIsLive((prev) => !prev);
  }, []);

  const reset = useCallback(() => {
    setData(initialData);
  }, [initialData]);

  return {
    data,
    isLive,
    toggleLive,
    reset,
    update,
  };
}

/**
 * Animate number changes with smooth transitions
 */
export function useAnimatedCounter(targetValue: number, duration: number = 1000) {
  const [displayValue, setDisplayValue] = useState(targetValue);

  useEffect(() => {
    const startValue = displayValue;
    const difference = targetValue - startValue;
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      // Easing function for smooth animation
      const easeOutQuad = 1 - (1 - progress) * (1 - progress);
      const currentValue = startValue + difference * easeOutQuad;
      
      setDisplayValue(Math.round(currentValue));

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [targetValue, duration]);

  return displayValue;
}
