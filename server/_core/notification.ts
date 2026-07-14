/**
 * notification.ts
 * Self-hosted owner notification — SMTP email + generic webhook fallback.
 * No external platform dependency.
 *
 * Env vars:
 *   SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS, SMTP_SECURE ("true"/"false")
 *   NOTIFY_EMAIL   — recipient address for SMTP delivery
 *   NOTIFY_WEBHOOK_URL — any HTTP webhook (Slack, Discord, custom)
 */
import { TRPCError } from "@trpc/server";
import { ENV } from "./env";

export type NotificationPayload = {
  title: string;
  content: string;
};

const TITLE_MAX_LENGTH = 1200;
const CONTENT_MAX_LENGTH = 20000;

const trimValue = (value: string): string => value.trim();
const isNonEmptyString = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0;

/** Send via SMTP using nodemailer (optional peer dep) */
async function sendEmail(payload: NotificationPayload): Promise<boolean> {
  const smtpHost = process.env.SMTP_HOST;
  const smtpUser = process.env.SMTP_USER;
  const smtpPass = process.env.SMTP_PASS ?? "";
  const notifyEmail = process.env.NOTIFY_EMAIL;
  if (!smtpHost || !notifyEmail) return false;
  try {
    // Dynamic import so nodemailer is optional — won't crash if not installed
    const nodemailer = await import("nodemailer").catch(() => null);
    if (!nodemailer) return false;
    const transporter = nodemailer.createTransport({
      host: smtpHost,
      port: parseInt(process.env.SMTP_PORT ?? "587", 10),
      secure: process.env.SMTP_SECURE === "true",
      auth: smtpUser ? { user: smtpUser, pass: smtpPass } : undefined,
    });
    await transporter.sendMail({
      from: smtpUser ?? notifyEmail,
      to: notifyEmail,
      subject: `[54Link] ${payload.title}`,
      text: payload.content,
      html: `<h2>${payload.title}</h2><pre style="white-space:pre-wrap">${payload.content}</pre>`,
    });
    return true;
  } catch (err) {
    console.warn("[Notification] SMTP delivery failed:", err);
    return false;
  }
}

/** Send via generic webhook (Slack, Discord, custom) */
async function sendWebhook(payload: NotificationPayload): Promise<boolean> {
  const webhookUrl = process.env.NOTIFY_WEBHOOK_URL;
  if (!webhookUrl) return false;
  try {
    const response = await fetch(webhookUrl, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        text: `*${payload.title}*\n${payload.content}`,
        title: payload.title,
        content: payload.content,
        timestamp: new Date().toISOString(),
      }),
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) {
      console.warn(`[Notification] Webhook delivery failed (${response.status})`);
      return false;
    }
    return true;
  } catch (err) {
    console.warn("[Notification] Webhook delivery failed:", err);
    return false;
  }
}

const validatePayload = (input: NotificationPayload): NotificationPayload => {
  if (!isNonEmptyString(input.title)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: "Notification title is required.",
    });
  }
  if (!isNonEmptyString(input.content)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: "Notification content is required.",
    });
  }

  const title = trimValue(input.title);
  const content = trimValue(input.content);

  if (title.length > TITLE_MAX_LENGTH) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Notification title must be at most ${TITLE_MAX_LENGTH} characters.`,
    });
  }

  if (content.length > CONTENT_MAX_LENGTH) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Notification content must be at most ${CONTENT_MAX_LENGTH} characters.`,
    });
  }

  return { title, content };
};

/**
 * Dispatches a project-owner notification.
 * Tries SMTP email first, then webhook, then falls back to console.log.
 * Returns `true` if at least one channel delivered successfully.
 * No external platform dependency.
 */
export async function notifyOwner(
  payload: NotificationPayload
): Promise<boolean> {
  const { title, content } = validatePayload(payload);

  // Try SMTP first
  if (await sendEmail({ title, content })) return true;

  // Try webhook second
  if (await sendWebhook({ title, content })) return true;

  // Always log as final fallback — never silently drop a notification
  console.info(`[Notification] OWNER ALERT — ${title}\n${content}`);
  return true;
}
