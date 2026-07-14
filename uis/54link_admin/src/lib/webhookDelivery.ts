import type { Alert } from './anomalyDetection';

export interface WebhookConfig {
  slackWebhookUrl?: string;
  pagerdutyKey?: string;
  teamsWebhookUrl?: string;
  genericWebhookUrl?: string;
}

/**
 * Deliver alert to Slack
 */
export async function deliverToSlack(alert: Alert, webhookUrl: string): Promise<boolean> {
  try {
    const color = {
      critical: 'danger',
      high: 'warning',
      medium: '#f59e0b',
      low: 'good',
    }[alert.severity];

    const payload = {
      text: `🚨 *${alert.title}*`,
      attachments: [{
        color,
        text: alert.message,
        fields: [
          { title: 'Severity', value: alert.severity.toUpperCase(), short: true },
          { title: 'Metric', value: alert.metric.replace(/_/g, ' ').toUpperCase(), short: true },
          { title: 'Current Value', value: alert.value.toLocaleString(), short: true },
          ...(alert.threshold ? [{ title: 'Threshold', value: alert.threshold.toLocaleString(), short: true }] : []),
          ...(alert.tenantId ? [{ title: 'Tenant', value: alert.tenantId, short: true }] : []),
        ],
        footer: '54link-dev Alert System',
        ts: Math.floor(alert.timestamp.getTime() / 1000),
      }],
    };

    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    return response.ok;
  } catch (error) {
    console.error('Failed to deliver to Slack:', error);
    return false;
  }
}

/**
 * Deliver alert to PagerDuty
 */
export async function deliverToPagerDuty(alert: Alert, integrationKey: string): Promise<boolean> {
  try {
    const severity = {
      critical: 'critical',
      high: 'error',
      medium: 'warning',
      low: 'info',
    }[alert.severity];

    const payload = {
      routing_key: integrationKey,
      event_action: 'trigger',
      dedup_key: alert.id,
      payload: {
        summary: alert.title,
        severity,
        source: '54link-dev Admin Dashboard',
        component: alert.metric,
        custom_details: {
          message: alert.message,
          current_value: alert.value,
          threshold: alert.threshold,
          tenant_id: alert.tenantId,
          alert_type: alert.type,
        },
      },
    };

    const response = await fetch('https://events.pagerduty.com/v2/enqueue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    return response.ok;
  } catch (error) {
    console.error('Failed to deliver to PagerDuty:', error);
    return false;
  }
}

/**
 * Deliver alert to Microsoft Teams
 */
export async function deliverToTeams(alert: Alert, webhookUrl: string): Promise<boolean> {
  try {
    const themeColor = {
      critical: 'FF0000',
      high: 'FF6B00',
      medium: 'F59E0B',
      low: '0078D4',
    }[alert.severity];

    const payload = {
      '@type': 'MessageCard',
      '@context': 'https://schema.org/extensions',
      summary: alert.title,
      themeColor,
      title: `🚨 ${alert.title}`,
      text: alert.message,
      sections: [{
        facts: [
          { name: 'Severity', value: alert.severity.toUpperCase() },
          { name: 'Metric', value: alert.metric.replace(/_/g, ' ').toUpperCase() },
          { name: 'Current Value', value: alert.value.toLocaleString() },
          ...(alert.threshold ? [{ name: 'Threshold', value: alert.threshold.toLocaleString() }] : []),
          ...(alert.tenantId ? [{ name: 'Tenant', value: alert.tenantId }] : []),
          { name: 'Time', value: alert.timestamp.toLocaleString() },
        ],
      }],
      potentialAction: [{
        '@type': 'OpenUri',
        name: 'View Dashboard',
        targets: [{
          os: 'default',
          uri: window.location.origin + '/usage-analytics',
        }],
      }],
    };

    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    return response.ok;
  } catch (error) {
    console.error('Failed to deliver to Teams:', error);
    return false;
  }
}

/**
 * Deliver alert to generic webhook
 */
export async function deliverToGenericWebhook(alert: Alert, webhookUrl: string): Promise<boolean> {
  try {
    const payload = {
      id: alert.id,
      type: alert.type,
      severity: alert.severity,
      title: alert.title,
      message: alert.message,
      metric: alert.metric,
      value: alert.value,
      threshold: alert.threshold,
      tenant_id: alert.tenantId,
      timestamp: alert.timestamp.toISOString(),
      source: '54link-dev Admin Dashboard',
    };

    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    return response.ok;
  } catch (error) {
    console.error('Failed to deliver to generic webhook:', error);
    return false;
  }
}

/**
 * Deliver alert to all configured webhooks with retry logic
 */
export async function deliverAlert(
  alert: Alert,
  config: WebhookConfig,
  maxRetries: number = 3
): Promise<{ success: boolean; results: Record<string, boolean> }> {
  const results: Record<string, boolean> = {};
  let overallSuccess = true;

  const deliveries: Array<{ name: string; fn: () => Promise<boolean> }> = [];

  if (config.slackWebhookUrl) {
    deliveries.push({
      name: 'slack',
      fn: () => deliverToSlack(alert, config.slackWebhookUrl!),
    });
  }

  if (config.pagerdutyKey) {
    deliveries.push({
      name: 'pagerduty',
      fn: () => deliverToPagerDuty(alert, config.pagerdutyKey!),
    });
  }

  if (config.teamsWebhookUrl) {
    deliveries.push({
      name: 'teams',
      fn: () => deliverToTeams(alert, config.teamsWebhookUrl!),
    });
  }

  if (config.genericWebhookUrl) {
    deliveries.push({
      name: 'generic',
      fn: () => deliverToGenericWebhook(alert, config.genericWebhookUrl!),
    });
  }

  // Deliver to all webhooks with retry logic
  for (const delivery of deliveries) {
    let success = false;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        success = await delivery.fn();
        if (success) break;
        
        // Exponential backoff
        if (attempt < maxRetries - 1) {
          await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
        }
      } catch (error) {
        console.error(`Attempt ${attempt + 1} failed for ${delivery.name}:`, error);
      }
    }
    
    results[delivery.name] = success;
    if (!success) overallSuccess = false;
  }

  return { success: overallSuccess, results };
}
