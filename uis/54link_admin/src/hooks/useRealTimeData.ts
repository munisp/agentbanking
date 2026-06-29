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
 * Generate realistic random variations for metrics
 */
export function generateVariation(
  baseValue: number,
  variationPercent: number = 2
): number {
  const variation = baseValue * (variationPercent / 100);
  const change = (Math.random() - 0.5) * 2 * variation;
  return Math.round(baseValue + change);
}

/**
 * Generate realistic growth trend (mostly positive with occasional dips)
 */
export function generateGrowthTrend(
  baseValue: number,
  growthRate: number = 0.5
): number {
  // 80% chance of growth, 20% chance of slight decline
  const isGrowth = Math.random() > 0.2;
  const maxChange = baseValue * (growthRate / 100);
  
  if (isGrowth) {
    return Math.round(baseValue + Math.random() * maxChange);
  } else {
    return Math.round(baseValue - Math.random() * maxChange * 0.3);
  }
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
