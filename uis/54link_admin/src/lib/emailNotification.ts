import type { Alert } from './anomalyDetection';

/**
 * Generate HTML email template for alert notifications
 */
export function generateAlertEmailHTML(alert: Alert): string {
  const severityColors = {
    critical: '#ef4444',
    high: '#f59e0b',
    medium: '#eab308',
    low: '#3b82f6',
  };

  const color = severityColors[alert.severity];

  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>54link-dev Alert Notification</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 30px; text-align: center;">
              <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: bold;">54link-dev</h1>
              <p style="margin: 10px 0 0 0; color: #e0e7ff; font-size: 14px;">Alert Notification System</p>
            </td>
          </tr>
          
          <!-- Alert Badge -->
          <tr>
            <td style="padding: 30px 40px 20px 40px; text-align: center;">
              <div style="display: inline-block; background-color: ${color}; color: #ffffff; padding: 8px 20px; border-radius: 20px; font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">
                ${alert.severity} ALERT
              </div>
            </td>
          </tr>
          
          <!-- Alert Content -->
          <tr>
            <td style="padding: 0 40px 30px 40px;">
              <h2 style="margin: 0 0 15px 0; color: #1f2937; font-size: 24px; font-weight: 600;">
                ${alert.title}
              </h2>
              <p style="margin: 0 0 25px 0; color: #4b5563; font-size: 16px; line-height: 1.6;">
                ${alert.message}
              </p>
              
              <!-- Alert Details -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f9fafb; border-radius: 6px; padding: 20px;">
                <tr>
                  <td style="padding: 8px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="color: #6b7280; font-size: 14px; font-weight: 600;">Alert Type:</td>
                        <td align="right" style="color: #1f2937; font-size: 14px;">${alert.type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 8px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="color: #6b7280; font-size: 14px; font-weight: 600;">Metric:</td>
                        <td align="right" style="color: #1f2937; font-size: 14px;">${alert.metric.replace(/_/g, ' ').toUpperCase()}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 8px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="color: #6b7280; font-size: 14px; font-weight: 600;">Current Value:</td>
                        <td align="right" style="color: #1f2937; font-size: 14px; font-weight: bold;">${alert.value.toLocaleString()}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                ${alert.threshold ? `
                <tr>
                  <td style="padding: 8px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="color: #6b7280; font-size: 14px; font-weight: 600;">Threshold:</td>
                        <td align="right" style="color: #1f2937; font-size: 14px;">${alert.threshold.toLocaleString()}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                ` : ''}
                ${alert.tenantId ? `
                <tr>
                  <td style="padding: 8px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="color: #6b7280; font-size: 14px; font-weight: 600;">Tenant ID:</td>
                        <td align="right" style="color: #1f2937; font-size: 14px;">${alert.tenantId}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                ` : ''}
                <tr>
                  <td style="padding: 8px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="color: #6b7280; font-size: 14px; font-weight: 600;">Detected At:</td>
                        <td align="right" style="color: #1f2937; font-size: 14px;">${alert.timestamp.toLocaleString()}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              
              <!-- CTA Button -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 30px;">
                <tr>
                  <td align="center">
                    <a href="${window.location.origin}/usage-analytics" style="display: inline-block; background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 6px; font-size: 16px; font-weight: 600;">
                      View Dashboard
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td style="background-color: #f9fafb; padding: 30px 40px; text-align: center; border-top: 1px solid #e5e7eb;">
              <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 14px;">
                This is an automated alert from 54link-dev Admin Dashboard
              </p>
              <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                © ${new Date().getFullYear()} 54link-dev. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
  `.trim();
}

/**
 * Generate plain text email for alert notifications (fallback)
 */
export function generateAlertEmailText(alert: Alert): string {
  return `
54link-dev ALERT NOTIFICATION
========================

SEVERITY: ${alert.severity.toUpperCase()}

${alert.title}

${alert.message}

DETAILS:
--------
Alert Type: ${alert.type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
Metric: ${alert.metric.replace(/_/g, ' ').toUpperCase()}
Current Value: ${alert.value.toLocaleString()}
${alert.threshold ? `Threshold: ${alert.threshold.toLocaleString()}` : ''}
${alert.tenantId ? `Tenant ID: ${alert.tenantId}` : ''}
Detected At: ${alert.timestamp.toLocaleString()}

View Dashboard: ${window.location.origin}/usage-analytics

---
This is an automated alert from 54link-dev Admin Dashboard
© ${new Date().getFullYear()} 54link-dev. All rights reserved.
  `.trim();
}

/**
 * Send email notification via backend API
 * In production, this would call a tRPC endpoint that uses SendGrid/AWS SES
 */
export async function sendEmailNotification(
  alert: Alert,
  recipients: string[]
): Promise<boolean> {
  try {
    const htmlContent = generateAlertEmailHTML(alert);
    const textContent = generateAlertEmailText(alert);

    // TODO: Replace with actual tRPC call
    // await trpc.notification.sendEmail.mutate({
    //   to: recipients,
    //   subject: `[${alert.severity.toUpperCase()}] ${alert.title}`,
    //   html: htmlContent,
    //   text: textContent,
    // });

    // Mock implementation for demo
    console.log('Email notification would be sent to:', recipients);
    console.log('Subject:', `[${alert.severity.toUpperCase()}] ${alert.title}`);
    console.log('HTML length:', htmlContent.length);
    console.log('Text length:', textContent.length);

    return true;
  } catch (error) {
    console.error('Failed to send email notification:', error);
    return false;
  }
}

/**
 * Batch send email notifications
 */
export async function sendBatchEmailNotifications(
  alerts: Alert[],
  recipients: string[]
): Promise<{ success: number; failed: number }> {
  let success = 0;
  let failed = 0;

  for (const alert of alerts) {
    const result = await sendEmailNotification(alert, recipients);
    if (result) {
      success++;
    } else {
      failed++;
    }
  }

  return { success, failed };
}
