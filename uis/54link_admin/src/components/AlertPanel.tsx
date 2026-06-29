import { AlertCircle, AlertTriangle, TrendingDown, TrendingUp, X } from 'lucide-react';
import { useState } from 'react';
import type { Alert } from '../lib/anomalyDetection';
import { getAlertColor, getAlertIcon } from '../lib/anomalyDetection';

interface AlertPanelProps {
  alerts: Alert[];
  onDismiss: (alertId: string) => void;
}

export default function AlertPanel({ alerts, onDismiss }: AlertPanelProps) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (alerts.length === 0) {
    return null;
  }

  const getIcon = (type: Alert['type']) => {
    switch (type) {
      case 'spike':
        return <TrendingUp className="w-5 h-5" />;
      case 'drop':
        return <TrendingDown className="w-5 h-5" />;
      case 'threshold':
        return <AlertTriangle className="w-5 h-5" />;
      case 'unusual_pattern':
        return <AlertCircle className="w-5 h-5" />;
      case 'error_rate':
        return <AlertTriangle className="w-5 h-5" />;
    }
  };

  return (
    <div className="space-y-3">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className={`${getAlertColor(alert.severity)} border-l-4 rounded-lg p-4 shadow-lg animate-in slide-in-from-right duration-300`}
        >
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3 flex-1">
              <div className="mt-0.5">
                {getIcon(alert.type)}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-2xl">{getAlertIcon(alert.type)}</span>
                  <h3 className="font-bold text-sm">{alert.title}</h3>
                  <span className="px-2 py-0.5 rounded-full text-xs font-semibold uppercase">
                    {alert.severity}
                  </span>
                </div>
                <p className="text-sm mb-2">{alert.message}</p>
                
                {expanded === alert.id && (
                  <div className="mt-3 pt-3 border-t border-current/20 text-xs space-y-1">
                    <div className="flex justify-between">
                      <span className="font-semibold">Metric:</span>
                      <span>{alert.metric.replace(/_/g, ' ').toUpperCase()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-semibold">Current Value:</span>
                      <span>{alert.value.toLocaleString()}</span>
                    </div>
                    {alert.threshold && (
                      <div className="flex justify-between">
                        <span className="font-semibold">Threshold:</span>
                        <span>{alert.threshold.toLocaleString()}</span>
                      </div>
                    )}
                    {alert.tenantId && (
                      <div className="flex justify-between">
                        <span className="font-semibold">Tenant:</span>
                        <span>{alert.tenantId}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="font-semibold">Detected:</span>
                      <span>{alert.timestamp.toLocaleTimeString()}</span>
                    </div>
                  </div>
                )}

                <button
                  onClick={() => setExpanded(expanded === alert.id ? null : alert.id)}
                  className="text-xs font-semibold mt-2 hover:underline"
                >
                  {expanded === alert.id ? 'Show less' : 'Show details'}
                </button>
              </div>
            </div>
            <button
              onClick={() => onDismiss(alert.id)}
              className="p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded transition-colors"
              title="Dismiss alert"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
