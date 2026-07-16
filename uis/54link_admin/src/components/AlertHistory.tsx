import { AlertCircle, AlertTriangle, Clock, TrendingDown, TrendingUp } from 'lucide-react';
import type { Alert } from '../lib/anomalyDetection';
import { getAlertColor } from '../lib/anomalyDetection';

interface AlertHistoryProps {
  alerts: Alert[];
}

export default function AlertHistory({ alerts }: AlertHistoryProps) {
  const getIcon = (type: Alert['type']) => {
    switch (type) {
      case 'spike':
        return <TrendingUp className="w-4 h-4" />;
      case 'drop':
        return <TrendingDown className="w-4 h-4" />;
      case 'threshold':
        return <AlertTriangle className="w-4 h-4" />;
      case 'unusual_pattern':
        return <AlertCircle className="w-4 h-4" />;
      case 'error_rate':
        return <AlertTriangle className="w-4 h-4" />;
    }
  };

  if (alerts.length === 0) {
    return (
      <div className="text-center py-12">
        <Clock className="w-12 h-12 text-slate-400 mx-auto mb-4" />
        <p className="text-slate-600 dark:text-slate-400">No alert history yet</p>
        <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
          Dismissed alerts will appear here
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className={`${getAlertColor(alert.severity)} border-l-4 rounded-lg p-3 opacity-75`}
        >
          <div className="flex items-start gap-3">
            <div className="mt-0.5">
              {getIcon(alert.type)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="font-semibold text-sm truncate">{alert.title}</h4>
                <span className="px-2 py-0.5 rounded-full text-xs font-semibold uppercase shrink-0">
                  {alert.severity}
                </span>
              </div>
              <p className="text-xs line-clamp-2">{alert.message}</p>
              <div className="flex items-center gap-4 mt-2 text-xs">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {alert.timestamp.toLocaleString()}
                </span>
                <span className="truncate">
                  {alert.metric.replace(/_/g, ' ').toUpperCase()}
                </span>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
