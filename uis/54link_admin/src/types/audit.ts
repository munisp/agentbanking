export type AuditEventType =
  | "TRANSFER"
  | "LOGIN"
  | "LOGOUT"
  | "CREATE"
  | "UPDATE"
  | "DELETE"
  | "WITHDRAWAL"
  | "DEPOSIT"
  | "ACCOUNT_CREATED"
  | "ACCOUNT_UPDATED"
  | "ACCOUNT_DELETED"
  | "USER_CREATED"
  | "USER_UPDATED"
  | "USER_DELETED"
  | "SETTINGS_CHANGED"
  | "PERMISSION_CHANGED"
  | string;

export interface AuditEventData {
  // Transfer events
  payee?: string;
  payer?: string;
  amount?: string;
  transaction_id?: string;

  // Login events
  type?: string;
  email?: string;

  // Generic event data
  [key: string]: unknown;
}

export interface AuditLog {
  id: string;
  actor_id: string;
  event_type: AuditEventType;
  timestamp: string;
  event_data: AuditEventData;
  tenant_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface AuditLogsResponse {
  data: AuditLog[];
  total: number;
  page: number;
  limit: number;
}

export interface AuditFilters {
  event_type?: AuditEventType;
  actor_id?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
  page?: number;
  limit?: number;
}
