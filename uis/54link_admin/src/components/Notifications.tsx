import { AlertCircle, Bell, CheckCircle, Clock, Info, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import apiClient from '../services/api';

interface ApiNotification {
  id: string;
  type: string;
  subject: string | null;
  message: string;
  status: 'pending' | 'sent' | 'failed';
  sent_at: string | null;
  created_at: string;
}

interface Notification {
  id: string;
  type: 'success' | 'warning' | 'info' | 'error';
  title: string;
  message: string;
  time: string;
  read: boolean;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const diffMs = Date.now() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
}

function mapStatus(status: string): Notification['type'] {
  if (status === 'sent') return 'success';
  if (status === 'failed') return 'error';
  return 'info';
}

function getTenantId(): string {
  try {
    const config = JSON.parse(localStorage.getItem('tenant_config') || '{}');
    return config?.tenant?.tenant_id || config?.tenant_id || '';
  } catch {
    return '';
  }
}

function getUserId(): string {
  try {
    const user = JSON.parse(localStorage.getItem('auth_user') || '{}');
    // Try multiple fallbacks: id > keycloak_id (in user) > keycloak_id (from localStorage) > email
    return user?.id || user?.keycloak_id || localStorage.getItem('keycloak_id') || user?.email || '';
  } catch {
    // Fallback to keycloak_id from localStorage
    return localStorage.getItem('keycloak_id') || '';
  }
}

export default function Notifications() {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const unreadCount = notifications.filter(n => !n.read).length;

  async function fetchNotifications() {
    const userId = getUserId();
    const tenantId = getTenantId();
    if (!userId || !tenantId) return;

    try {
      setLoading(true);
      const { data } = await apiClient.get<{ notifications: ApiNotification[] }>(
        `/notification/api/v1/notifications/${userId}`,
        { params: { tenant_id: tenantId, limit: 20 } }
      );
      const incoming = data.notifications || [];
      setNotifications(prev => {
        const readMap = new Map(prev.map(p => [p.id, p.read]));
        return incoming.map(n => ({
          id: n.id,
          type: mapStatus(n.status),
          title: n.subject || 'Notification',
          message: n.message,
          time: formatRelativeTime(n.created_at),
          read: readMap.get(n.id) ?? false,
        }));
      });
    } catch {
      // Notifications are non-critical; swallow errors silently
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchNotifications();
    intervalRef.current = setInterval(fetchNotifications, 30000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const getIcon = (type: string) => {
    switch (type) {
      case 'success': return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'warning': return <AlertCircle className="w-5 h-5 text-yellow-600" />;
      case 'error': return <AlertCircle className="w-5 h-5 text-red-600" />;
      default: return <Info className="w-5 h-5 text-blue-600" />;
    }
  };

  const getBgColor = (type: string) => {
    switch (type) {
      case 'success': return 'bg-green-50 dark:bg-green-900/20';
      case 'warning': return 'bg-yellow-50 dark:bg-yellow-900/20';
      case 'error': return 'bg-red-50 dark:bg-red-900/20';
      default: return 'bg-blue-50 dark:bg-blue-900/20';
    }
  };

  const markAsRead = (id: string) => {
    setNotifications(notifications.map(n => n.id === id ? { ...n, read: true } : n));
  };

  const markAllAsRead = () => {
    setNotifications(notifications.map(n => ({ ...n, read: true })));
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
      >
        <Bell className="w-6 h-6 text-gray-700 dark:text-gray-300" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 w-5 h-5 bg-red-600 text-white text-xs font-bold rounded-full flex items-center justify-center">
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          <div className="absolute -right-50 mt-2 w-96 bg-white dark:bg-slate-800 rounded-xl shadow-2xl border border-gray-200 dark:border-slate-700 z-50">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-slate-700">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">Notifications</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">{unreadCount} unread</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={markAllAsRead}
                  className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  Mark all read
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 hover:bg-gray-100 dark:hover:bg-slate-700 rounded"
                >
                  <X className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                </button>
              </div>
            </div>

            <div className="max-h-96 overflow-y-auto">
              {loading && notifications.length === 0 && (
                <div className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">Loading...</div>
              )}
              {!loading && notifications.length === 0 && (
                <div className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">No notifications</div>
              )}
              {notifications.map((notification) => (
                <div
                  key={notification.id}
                  onClick={() => markAsRead(notification.id)}
                  className={`p-4 border-b border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors ${
                    !notification.read ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''
                  }`}
                >
                  <div className="flex gap-3">
                    <div className={`p-2 rounded-lg ${getBgColor(notification.type)} flex-shrink-0`}>
                      {getIcon(notification.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="font-semibold text-gray-900 dark:text-white text-sm">
                          {notification.title}
                        </h4>
                        {!notification.read && (
                          <div className="w-2 h-2 bg-blue-600 rounded-full flex-shrink-0 mt-1" />
                        )}
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        {notification.message}
                      </p>
                      <div className="flex items-center gap-1 mt-2 text-xs text-gray-500 dark:text-gray-500">
                        <Clock className="w-3 h-3" />
                        {notification.time}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-3 border-t border-gray-200 dark:border-slate-700 text-center">
              <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">
                View all notifications
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
