/**
 * Anomaly Detection Utility for Usage Analytics
 * Detects unusual patterns in API usage and generates alerts
 */

export interface Alert {
  id: string;
  type: 'spike' | 'drop' | 'threshold' | 'unusual_pattern' | 'error_rate';
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  message: string;
  timestamp: Date;
  metric: string;
  value: number;
  threshold?: number;
  tenantId?: string;
  // Acknowledgment workflow fields
  status?: 'new' | 'acknowledged' | 'resolved';
  acknowledgedAt?: Date;
  acknowledgedBy?: string;
  assignedTo?: string;
  resolvedAt?: Date;
  resolvedBy?: string;
  resolutionNotes?: string;
}

interface DataPoint {
  value: number;
  timestamp: Date;
}

/**
 * Calculate standard deviation of a dataset
 */
function calculateStdDev(values: number[]): number {
  if (values.length === 0) return 0;
  const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
  const squaredDiffs = values.map(val => Math.pow(val - mean, 2));
  const variance = squaredDiffs.reduce((sum, val) => sum + val, 0) / values.length;
  return Math.sqrt(variance);
}

/**
 * Calculate mean of a dataset
 */
function calculateMean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, val) => sum + val, 0) / values.length;
}

/**
 * Detect sudden spikes in API calls (> 3 standard deviations from mean)
 */
export function detectSpike(
  data: DataPoint[],
  threshold: number = 3
): Alert | null {
  if (data.length < 5) return null; // Need enough data points

  const values = data.map(d => d.value);
  const mean = calculateMean(values);
  const stdDev = calculateStdDev(values);
  
  const latestValue = values[values.length - 1];
  const zScore = (latestValue - mean) / (stdDev || 1);

  if (zScore > threshold) {
    const percentIncrease = ((latestValue - mean) / mean * 100).toFixed(1);
    return {
      id: `spike-${Date.now()}`,
      type: 'spike',
      severity: zScore > 5 ? 'critical' : zScore > 4 ? 'high' : 'medium',
      title: 'Unusual API Call Spike Detected',
      message: `API calls increased by ${percentIncrease}% (${latestValue.toLocaleString()} calls vs ${mean.toFixed(0)} average). This is ${zScore.toFixed(1)} standard deviations above normal.`,
      timestamp: new Date(),
      metric: 'api_calls',
      value: latestValue,
      threshold: mean + (threshold * stdDev),
    };
  }

  return null;
}

/**
 * Detect sudden drops in API calls
 */
export function detectDrop(
  data: DataPoint[],
  threshold: number = 2.5
): Alert | null {
  if (data.length < 5) return null;

  const values = data.map(d => d.value);
  const mean = calculateMean(values);
  const stdDev = calculateStdDev(values);
  
  const latestValue = values[values.length - 1];
  const zScore = (mean - latestValue) / (stdDev || 1);

  if (zScore > threshold && latestValue < mean * 0.5) {
    const percentDecrease = ((mean - latestValue) / mean * 100).toFixed(1);
    return {
      id: `drop-${Date.now()}`,
      type: 'drop',
      severity: zScore > 4 ? 'critical' : 'high',
      title: 'Significant API Call Drop Detected',
      message: `API calls dropped by ${percentDecrease}% (${latestValue.toLocaleString()} calls vs ${mean.toFixed(0)} average). Possible service disruption.`,
      timestamp: new Date(),
      metric: 'api_calls',
      value: latestValue,
      threshold: mean - (threshold * stdDev),
    };
  }

  return null;
}

/**
 * Detect threshold breaches
 */
export function detectThresholdBreach(
  value: number,
  threshold: number,
  metric: string,
  metricLabel: string
): Alert | null {
  if (value > threshold) {
    const percentOver = ((value - threshold) / threshold * 100).toFixed(1);
    return {
      id: `threshold-${metric}-${Date.now()}`,
      type: 'threshold',
      severity: value > threshold * 1.5 ? 'critical' : 'high',
      title: `${metricLabel} Threshold Exceeded`,
      message: `${metricLabel} is at ${value.toLocaleString()}, which is ${percentOver}% above the threshold of ${threshold.toLocaleString()}.`,
      timestamp: new Date(),
      metric,
      value,
      threshold,
    };
  }

  return null;
}

/**
 * Detect unusual patterns in tenant activity
 */
export function detectUnusualTenantActivity(
  tenantId: string,
  currentCalls: number,
  historicalAverage: number,
  threshold: number = 5
): Alert | null {
  const ratio = currentCalls / (historicalAverage || 1);

  if (ratio > threshold) {
    return {
      id: `tenant-${tenantId}-${Date.now()}`,
      type: 'unusual_pattern',
      severity: ratio > 10 ? 'critical' : ratio > 7 ? 'high' : 'medium',
      title: 'Unusual Tenant Activity',
      message: `Tenant ${tenantId} is making ${ratio.toFixed(1)}x more API calls than usual (${currentCalls.toLocaleString()} vs ${historicalAverage.toFixed(0)} average). Possible abuse or integration issue.`,
      timestamp: new Date(),
      metric: 'tenant_activity',
      value: currentCalls,
      threshold: historicalAverage * threshold,
      tenantId,
    };
  }

  return null;
}

/**
 * Detect high error rates
 */
export function detectHighErrorRate(
  errorCount: number,
  totalCalls: number,
  threshold: number = 0.05 // 5% error rate
): Alert | null {
  if (totalCalls === 0) return null;

  const errorRate = errorCount / totalCalls;

  if (errorRate > threshold) {
    return {
      id: `error-rate-${Date.now()}`,
      type: 'error_rate',
      severity: errorRate > 0.2 ? 'critical' : errorRate > 0.1 ? 'high' : 'medium',
      title: 'High Error Rate Detected',
      message: `Error rate is ${(errorRate * 100).toFixed(1)}% (${errorCount.toLocaleString()} errors out of ${totalCalls.toLocaleString()} calls). This exceeds the ${(threshold * 100).toFixed(0)}% threshold.`,
      timestamp: new Date(),
      metric: 'error_rate',
      value: errorRate,
      threshold,
    };
  }

  return null;
}

/**
 * Analyze usage data and detect all anomalies
 */
export function analyzeUsageData(data: {
  trends: Array<{ date: string; count: number }>;
  totalEvents: number;
  byTenant?: Array<{ tenantId: string; totalEvents: number; avgEvents?: number }>;
  errorCount?: number;
}): Alert[] {
  const alerts: Alert[] = [];

  // Convert trends to data points
  const dataPoints: DataPoint[] = data.trends.map(t => ({
    value: t.count,
    timestamp: new Date(t.date),
  }));

  // Detect spikes
  const spikeAlert = detectSpike(dataPoints);
  if (spikeAlert) alerts.push(spikeAlert);

  // Detect drops
  const dropAlert = detectDrop(dataPoints);
  if (dropAlert) alerts.push(dropAlert);

  // Detect threshold breaches (example: 100k calls per hour)
  const thresholdAlert = detectThresholdBreach(
    data.totalEvents,
    100000,
    'total_api_calls',
    'Total API Calls'
  );
  if (thresholdAlert) alerts.push(thresholdAlert);

  // Detect unusual tenant activity
  if (data.byTenant) {
    data.byTenant.forEach(tenant => {
      if (tenant.avgEvents) {
        const tenantAlert = detectUnusualTenantActivity(
          tenant.tenantId,
          tenant.totalEvents,
          tenant.avgEvents
        );
        if (tenantAlert) alerts.push(tenantAlert);
      }
    });
  }

  // Detect high error rates
  if (data.errorCount !== undefined) {
    const errorAlert = detectHighErrorRate(data.errorCount, data.totalEvents);
    if (errorAlert) alerts.push(errorAlert);
  }

  return alerts;
}

/**
 * Get alert severity color
 */
export function getAlertColor(severity: Alert['severity']): string {
  switch (severity) {
    case 'critical':
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border-red-500';
    case 'high':
      return 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300 border-orange-500';
    case 'medium':
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300 border-yellow-500';
    case 'low':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-500';
  }
}

/**
 * Get alert icon
 */
export function getAlertIcon(type: Alert['type']): string {
  switch (type) {
    case 'spike':
      return '📈';
    case 'drop':
      return '📉';
    case 'threshold':
      return '⚠️';
    case 'unusual_pattern':
      return '🔍';
    case 'error_rate':
      return '❌';
  }
}
