import { Activity } from 'lucide-react';

interface LiveIndicatorProps {
  isLive: boolean;
  onToggle?: () => void;
}

export function LiveIndicator({ isLive, onToggle }: LiveIndicatorProps) {
  return (
    <button
      onClick={onToggle}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
        isLive
          ? 'bg-green-100 text-green-700 hover:bg-green-200'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
    >
      <Activity className={`w-4 h-4 ${isLive ? 'animate-pulse' : ''}`} />
      <span>{isLive ? 'Live' : 'Paused'}</span>
      {isLive && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
        </span>
      )}
    </button>
  );
}
