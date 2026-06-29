import type { Alert } from '@/lib/anomalyDetection';
import { Check, FileText, UserPlus, X } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

interface AlertAcknowledgmentProps {
  alert: Alert | {
    id: string;
    title?: string;
    message?: string;
    type?: string;
    severity?: string;
    timestamp?: Date | string;
    status?: string;
    acknowledgedAt?: Date | string;
    acknowledgedBy?: string;
    assignedTo?: string;
    resolvedAt?: Date | string;
    resolvedBy?: string;
    resolutionNotes?: string;
  };
  onAcknowledge: (alertId: string, assignedTo: string) => void;
  onResolve: (alertId: string, notes: string) => void;
  onClose: () => void;
}

export default function AlertAcknowledgment({
  alert,
  onAcknowledge,
  onResolve,
  onClose,
}: AlertAcknowledgmentProps) {
  const [assignedTo, setAssignedTo] = useState(alert.assignedTo || '');
  const [resolutionNotes, setResolutionNotes] = useState(alert.resolutionNotes || '');
  const [mode, setMode] = useState<'acknowledge' | 'resolve'>('acknowledge');

  const handleAcknowledge = () => {
    if (!assignedTo.trim()) {
      toast.error('Please enter an assignee');
      return;
    }
    onAcknowledge(alert.id, assignedTo);
    toast.success('Alert acknowledged successfully');
    onClose();
  };

  const handleResolve = () => {
    if (!resolutionNotes.trim()) {
      toast.error('Please enter resolution notes');
      return;
    }
    onResolve(alert.id, resolutionNotes);
    toast.success('Alert resolved successfully');
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
            {mode === 'acknowledge' ? 'Acknowledge Alert' : 'Resolve Alert'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-600 dark:text-slate-400" />
          </button>
        </div>

        {/* Alert Details */}
        <div className="p-6 space-y-4">
          <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-4">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
              {alert.title}
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {alert.message}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {alert.type && (
                <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs font-medium">
                  {alert.type.replace(/_/g, ' ').toUpperCase()}
                </span>
              )}
              {alert.severity && (
                <span className="px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded text-xs font-medium">
                  {alert.severity.toUpperCase()}
                </span>
              )}
              {alert.timestamp && (
                <span className="px-2 py-1 bg-slate-100 dark:bg-slate-600 text-slate-700 dark:text-slate-300 rounded text-xs">
                  {(alert.timestamp instanceof Date ? alert.timestamp : new Date(alert.timestamp)).toLocaleString()}
                </span>
              )}
            </div>
          </div>

          {/* Status */}
          {alert.status && (
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium text-slate-700 dark:text-slate-300">
                Current Status:
              </span>
              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                alert.status === 'new' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300' :
                alert.status === 'acknowledged' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
              }`}>
                {alert.status.toUpperCase()}
              </span>
            </div>
          )}

          {/* Mode Toggle */}
          <div className="flex gap-2">
            <button
              onClick={() => setMode('acknowledge')}
              className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                mode === 'acknowledge'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              <Check className="w-4 h-4 inline mr-2" />
              Acknowledge
            </button>
            <button
              onClick={() => setMode('resolve')}
              className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                mode === 'resolve'
                  ? 'bg-green-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              <FileText className="w-4 h-4 inline mr-2" />
              Resolve
            </button>
          </div>

          {/* Acknowledge Form */}
          {mode === 'acknowledge' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  <UserPlus className="w-4 h-4 inline mr-1" />
                  Assign To
                </label>
                <input
                  type="text"
                  value={assignedTo}
                  onChange={(e) => setAssignedTo(e.target.value)}
                  placeholder="Enter name or email"
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Who will be responsible for investigating this alert?
                </p>
              </div>

              {alert.acknowledgedAt && (
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                  <p className="text-sm text-blue-700 dark:text-blue-300">
                    <strong>Previously acknowledged:</strong> {(alert.acknowledgedAt instanceof Date ? alert.acknowledgedAt : new Date(alert.acknowledgedAt)).toLocaleString()}
                    {alert.acknowledgedBy && ` by ${alert.acknowledgedBy}`}
                  </p>
                </div>
              )}

              <button
                onClick={handleAcknowledge}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                <Check className="w-5 h-5" />
                Acknowledge Alert
              </button>
            </div>
          )}

          {/* Resolve Form */}
          {mode === 'resolve' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  <FileText className="w-4 h-4 inline mr-1" />
                  Resolution Notes
                </label>
                <textarea
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  placeholder="Describe how this alert was resolved..."
                  rows={5}
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
                />
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Document the root cause and actions taken to resolve this alert.
                </p>
              </div>

              {alert.resolvedAt && (
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
                  <p className="text-sm text-green-700 dark:text-green-300">
                    <strong>Previously resolved:</strong> {(alert.resolvedAt instanceof Date ? alert.resolvedAt : new Date(alert.resolvedAt)).toLocaleString()}
                    {alert.resolvedBy && ` by ${alert.resolvedBy}`}
                  </p>
                  {alert.resolutionNotes && (
                    <p className="text-sm text-green-600 dark:text-green-400 mt-2">
                      "{alert.resolutionNotes}"
                    </p>
                  )}
                </div>
              )}

              <button
                onClick={handleResolve}
                className="w-full py-3 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                <Check className="w-5 h-5" />
                Resolve Alert
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
