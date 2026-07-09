/**
 * Cursor-based Pagination — for high-volume endpoints
 *
 * Usage:
 *   const result = await cursorPaginate(db, transactions, {
 *     cursor: input.cursor,
 *     limit: input.limit,
 *     orderBy: transactions.createdAt,
 *     direction: 'desc',
 *   });
 */
import { sql, gt, lt, desc, asc } from "drizzle-orm";

interface CursorPaginationOptions {
  cursor?: string | null;
  limit: number;
  orderBy: any;
  direction: "asc" | "desc";
}

interface CursorPaginationResult<T> {
  items: T[];
  nextCursor: string | null;
  hasMore: boolean;
}

export function encodeCursor(value: string | number | Date): string {
  const str = value instanceof Date ? value.toISOString() : String(value);
  return Buffer.from(str).toString("base64url");
}

export function decodeCursor(cursor: string): string {
  return Buffer.from(cursor, "base64url").toString();
}

export function buildCursorResult<T extends Record<string, unknown>>(
  items: T[],
  limit: number,
  cursorField: string
): CursorPaginationResult<T> {
  const hasMore = items.length > limit;
  const trimmed = hasMore ? items.slice(0, limit) : items;
  const lastItem = trimmed[trimmed.length - 1];
  const nextCursor = lastItem
    ? encodeCursor(String(lastItem[cursorField]))
    : null;

  return {
    items: trimmed,
    nextCursor: hasMore ? nextCursor : null,
    hasMore,
  };
}
