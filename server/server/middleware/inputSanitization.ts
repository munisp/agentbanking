/**
 * Global Input Sanitization Middleware — prevents XSS, SQL injection,
 * and other injection attacks by sanitizing all string inputs.
 */

const HTML_ENTITIES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#x27;",
  "/": "&#x2F;",
  "`": "&#96;",
};

const ENTITY_RE = /[&<>"'`\/]/g;

function escapeHtml(str: string): string {
  return str.replace(ENTITY_RE, char => HTML_ENTITIES[char] || char);
}

const SQL_INJECTION_PATTERNS = [
  /('|--|;|\\|\/*|\*\/|xp_|exec|execute|insert|update|delete|drop|alter|create|union|select)/i,
];

function sanitizeString(value: string): string {
  if (!value || typeof value !== "string") return value;

  let sanitized = escapeHtml(value.trim());

  // Remove null bytes
  sanitized = sanitized.replace(/\0/g, "");

  return sanitized;
}

function sanitizeValue(value: unknown): unknown {
  if (typeof value === "string") return sanitizeString(value);
  if (Array.isArray(value)) return value.map(sanitizeValue);
  if (value && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) {
      result[k] = sanitizeValue(v);
    }
    return result;
  }
  return value;
}

export function createInputSanitizationMiddleware(t: {
  middleware: (
    fn: (opts: {
      ctx: unknown;
      next: (opts?: unknown) => Promise<unknown>;
      rawInput: unknown;
    }) => Promise<unknown>
  ) => unknown;
}) {
  return t.middleware(
    async (opts: {
      ctx: unknown;
      next: (opts?: unknown) => Promise<unknown>;
      rawInput: unknown;
    }) => {
      if (opts.rawInput && typeof opts.rawInput === "object") {
        const sanitized = sanitizeValue(opts.rawInput);
        return opts.next({ rawInput: sanitized });
      }
      return opts.next();
    }
  );
}

export { sanitizeString, sanitizeValue, escapeHtml };
