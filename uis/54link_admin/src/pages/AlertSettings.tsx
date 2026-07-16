import { Settings, Bell, Mail, Webhook, Save, TestTube } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

interface AlertConfig {
  spikeThreshold: number;
  dropThreshold: number;
  errorRateThreshold: number;
  tenantActivityThreshold: number;
  totalCallsThreshold: number;
  enabledAlerts: {
    spike: boolean;
    drop: boolean;
    threshold: boolean;
    unusualPattern: boolean;
    errorRate: boolean;
  };
  notifications: {
    email: boolean;
    sms: boolean;
    webhook: boolean;
  };
  emailRecipients: string;
  webhookUrl: string;
  slackWebhookUrl: string;
  pagerdutyKey: string;
  teamsWebhookUrl: string;
}

const DEFAULT_CONFIG: AlertConfig = {
  spikeThreshold: 3,
  dropThreshold: 2.5,
  errorRateThreshold: 0.05,
  tenantActivityThreshold: 5,
  totalCallsThreshold: 100000,
  enabledAlerts: {
    spike: true,
    drop: true,
    threshold: true,
    unusualPattern: true,
    errorRate: true,
  },
  notifications: {
    email: false,
    sms: false,
    webhook: false,
  },
  emailRecipients: '',
  webhookUrl: '',
  slackWebhookUrl: '',
  pagerdutyKey: '',
  teamsWebhookUrl: '',
};

export default function AlertSettings() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [config, setConfig] = useState<AlertConfig>(() => {
    const saved = localStorage.getItem('alertConfig');
    return saved ? JSON.parse(saved) : DEFAULT_CONFIG;
  });

  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Save to localStorage (in production, save to database via tRPC)
      localStorage.setItem('alertConfig', JSON.stringify(config));
      
      // TODO: Save to database
      // await trpc.alert.updateConfig.mutate(config);
      
      toast.success('Alert settings saved successfully');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestWebhook = async (type: 'slack' | 'pagerduty' | 'teams') => {
    setIsTesting(true);
    try {
      const testPayload = {
        title: 'Test Alert',
        message: 'This is a test alert from 54link-dev Admin Dashboard',
        severity: 'medium',
        timestamp: new Date().toISOString(),
      };

      let url = '';
      let body: any = testPayload;

      switch (type) {
        case 'slack':
          url = config.slackWebhookUrl;
          body = {
            text: `🔔 *${testPayload.title}*`,
            attachments: [{
              color: '#f59e0b',
              text: testPayload.message,
              footer: '54link-dev Alert System',
              ts: Math.floor(new Date().getTime() / 1000),
            }],
          };
          break;
        case 'pagerduty':
          // PagerDuty Events API v2
          body = {
            routing_key: config.pagerdutyKey,
            event_action: 'trigger',
            payload: {
              summary: testPayload.title,
              severity: testPayload.severity,
              source: '54link-dev Admin Dashboard',
              custom_details: testPayload,
            },
          };
          url = 'https://events.pagerduty.com/v2/enqueue';
          break;
        case 'teams':
          url = config.teamsWebhookUrl;
          body = {
            '@type': 'MessageCard',
            '@context': 'https://schema.org/extensions',
            summary: testPayload.title,
            themeColor: 'f59e0b',
            title: testPayload.title,
            text: testPayload.message,
            sections: [{
              facts: [
                { name: 'Severity', value: testPayload.severity },
                { name: 'Time', value: new Date().toLocaleString() },
              ],
            }],
          };
          break;
      }

      if (!url) {
        toast.error(`Please configure ${type} webhook URL first`);
        return;
      }

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (response.ok) {
        toast.success(`Test alert sent to ${type} successfully`);
      } else {
        toast.error(`Failed to send test alert to ${type}`);
      }
    } catch (error) {
      toast.error(`Error testing ${type} webhook`);
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div 
      className="min-h-screen dark:from-slate-900 dark:to-slate-800"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`
      }}
    >
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
        <div className="container py-6">
          <div className="flex items-center gap-3">
            <Settings className="w-8 h-8" style={{ color: primaryColor }} />
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
                Alert Settings
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                Configure alert thresholds and notification preferences
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="container py-8 space-y-6">
        {/* Alert Thresholds */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
            <Bell className="w-5 h-5" />
            Alert Thresholds
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                Spike Detection Threshold (Standard Deviations)
              </label>
              <input
                type="number"
                step="0.1"
                value={config.spikeThreshold}
                onChange={(e) => setConfig({ ...config, spikeThreshold: parseFloat(e.target.value) })}
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
              />
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Higher values = less sensitive (default: 3.0)
              </p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                Drop Detection Threshold (Standard Deviations)
              </label>
              <input
                type="number"
                step="0.1"
                value={config.dropThreshold}
                onChange={(e) => setConfig({ ...config, dropThreshold: parseFloat(e.target.value) })}
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
              />
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Lower values = more sensitive (default: 2.5)
              </p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                Error Rate Threshold (Percentage)
              </label>
              <input
                type="number"
                step="0.01"
                value={config.errorRateThreshold * 100}
                onChange={(e) => setConfig({ ...config, errorRateThreshold: parseFloat(e.target.value) / 100 })}
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
              />
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Alert when error rate exceeds this % (default: 5%)
              </p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                Tenant Activity Multiplier
              </label>
              <input
                type="number"
                step="0.5"
                value={config.tenantActivityThreshold}
                onChange={(e) => setConfig({ ...config, tenantActivityThreshold: parseFloat(e.target.value) })}
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
              />
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Alert when tenant exceeds Nx normal activity (default: 5x)
              </p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                Total API Calls Threshold
              </label>
              <input
                type="number"
                step="10000"
                value={config.totalCallsThreshold}
                onChange={(e) => setConfig({ ...config, totalCallsThreshold: parseInt(e.target.value) })}
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
              />
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Alert when total calls exceed this number (default: 100,000)
              </p>
            </div>
          </div>
        </div>

        {/* Enable/Disable Alerts */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">
            Alert Types
          </h2>

          <div className="space-y-4">
            {Object.entries(config.enabledAlerts).map(([key, enabled]) => (
              <label key={key} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setConfig({
                    ...config,
                    enabledAlerts: { ...config.enabledAlerts, [key]: e.target.checked },
                  })}
                  className="w-5 h-5 rounded"
                  style={{ accentColor: primaryColor }}
                />
                <span className="text-slate-900 dark:text-white font-medium capitalize">
                  {key.replace(/([A-Z])/g, ' $1').trim()} Alerts
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Notification Preferences */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
            <Mail className="w-5 h-5" />
            Notification Channels
          </h2>

          <div className="space-y-6">
            {/* Email */}
            <div>
              <label className="flex items-center gap-3 cursor-pointer mb-3">
                <input
                  type="checkbox"
                  checked={config.notifications.email}
                  onChange={(e) => setConfig({
                    ...config,
                    notifications: { ...config.notifications, email: e.target.checked },
                  })}
                  className="w-5 h-5 rounded"
                  style={{ accentColor: primaryColor }}
                />
                <span className="text-slate-900 dark:text-white font-medium">Email Notifications</span>
              </label>
              {config.notifications.email && (
                <input
                  type="text"
                  placeholder="admin@54link-dev.com, ops@54link-dev.com"
                  value={config.emailRecipients}
                  onChange={(e) => setConfig({ ...config, emailRecipients: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
              )}
            </div>

            {/* Webhook */}
            <div>
              <label className="flex items-center gap-3 cursor-pointer mb-3">
                <input
                  type="checkbox"
                  checked={config.notifications.webhook}
                  onChange={(e) => setConfig({
                    ...config,
                    notifications: { ...config.notifications, webhook: e.target.checked },
                  })}
                  className="w-5 h-5 rounded"
                  style={{ accentColor: primaryColor }}
                />
                <span className="text-slate-900 dark:text-white font-medium">Generic Webhook</span>
              </label>
              {config.notifications.webhook && (
                <input
                  type="url"
                  placeholder="https://your-webhook-url.com/alerts"
                  value={config.webhookUrl}
                  onChange={(e) => setConfig({ ...config, webhookUrl: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
              )}
            </div>
          </div>
        </div>

        {/* External Integrations */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
            <Webhook className="w-5 h-5" />
            External Integrations
          </h2>

          <div className="space-y-6">
            {/* Slack */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                Slack Webhook URL
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  placeholder="https://hooks.slack.com/services/..."
                  value={config.slackWebhookUrl}
                  onChange={(e) => setConfig({ ...config, slackWebhookUrl: e.target.value })}
                  className="flex-1 px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
                <button
                  onClick={() => handleTestWebhook('slack')}
                  disabled={!config.slackWebhookUrl || isTesting}
                  className="px-4 py-2 text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  style={{ backgroundColor: secondaryColor }}
                >
                  <TestTube className="w-4 h-4" />
                  Test
                </button>
              </div>
            </div>

            {/* PagerDuty */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                PagerDuty Integration Key
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="R0XXXXXXXXXXXXXXXXXXXXX"
                  value={config.pagerdutyKey}
                  onChange={(e) => setConfig({ ...config, pagerdutyKey: e.target.value })}
                  className="flex-1 px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
                <button
                  onClick={() => handleTestWebhook('pagerduty')}
                  disabled={!config.pagerdutyKey || isTesting}
                  className="px-4 py-2 text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  style={{ backgroundColor: secondaryColor }}
                >
                  <TestTube className="w-4 h-4" />
                  Test
                </button>
              </div>
            </div>

            {/* Microsoft Teams */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                Microsoft Teams Webhook URL
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  placeholder="https://outlook.office.com/webhook/..."
                  value={config.teamsWebhookUrl}
                  onChange={(e) => setConfig({ ...config, teamsWebhookUrl: e.target.value })}
                  className="flex-1 px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                />
                <button
                  onClick={() => handleTestWebhook('teams')}
                  disabled={!config.teamsWebhookUrl || isTesting}
                  className="px-4 py-2 text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  style={{ backgroundColor: secondaryColor }}
                >
                  <TestTube className="w-4 h-4" />
                  Test
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-6 py-3 text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-semibold"
            style={{ backgroundColor: primaryColor }}
          >
            <Save className="w-5 h-5" />
            {isSaving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
}
