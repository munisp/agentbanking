/**
 * Shared router helpers — common validation, status transition, and pagination
 * utilities used across all 477 tRPC routers.
 *
 * Extracted to eliminate duplicated boilerplate while preserving behavior.
 */

/**
 * Validates generic input data — checks for non-null, non-empty fields,
 * valid ID values, and valid amount ranges.
 */
export function validateInput(data: Record<string, unknown>): boolean {
  if (!data) return false;
  const requiredFields = Object.keys(data).filter(
    k => data[k] !== undefined && data[k] !== null
  );
  if (requiredFields.length === 0) return false;
  if (
    typeof data.id === "number" &&
    (data.id <= 0 || !Number.isFinite(data.id))
  )
    return false;
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 ||
      data.amount > 100_000_000 ||
      !Number.isFinite(data.amount))
  )
    return false;
  return true;
}

/**
 * Validates a status transition against a transitions map.
 * Returns true if the transition from currentStatus to newStatus is allowed.
 */
export function isValidTransition(
  transitions: Record<string, string[]>,
  currentStatus: string,
  newStatus: string
): boolean {
  const allowed = transitions[currentStatus];
  if (!allowed) return false;
  return allowed.includes(newStatus);
}

/**
 * Builds a standard paginated response wrapper.
 */
export function paginatedResponse<T>(
  items: T[],
  total: number,
  page: number,
  limit: number
) {
  return {
    items,
    total,
    page,
    limit,
    totalPages: Math.ceil(total / limit),
    hasMore: page * limit < total,
  };
}

/**
 * Generates a unique idempotency key for deduplication.
 */
export function generateIdempotencyKey(
  resource: string,
  action: string,
  userId?: string
): string {
  const ts = Date.now();
  const rand = (crypto.getRandomValues(new Uint32Array(1))[0] / 4294967295).toString(36).slice(2, 10);
  return `${resource}:${action}:${userId || "system"}:${ts}:${rand}`;
}

/**
 * Standard error response builder for consistent error formatting.
 */
export function buildErrorResponse(code: string, message: string) {
  return {
    success: false,
    error: { code, message },
    timestamp: new Date().toISOString(),
  };
}

/**
 * Standard success response builder.
 */
export function buildSuccessResponse<T>(data: T, message?: string) {
  return {
    success: true,
    data,
    message: message || "Operation completed successfully",
    timestamp: new Date().toISOString(),
  };
}
