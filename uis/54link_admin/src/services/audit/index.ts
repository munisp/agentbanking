import type { AuditFilters, AuditLog, AuditLogsResponse } from "../../types/audit";
import apiClient from "../api";

const AUDIT_BASE_URL = "/audit";

export const auditService = {
  /**
   * Fetch all audit logs with optional filters and pagination
   */
  async getAuditLogs(filters?: AuditFilters): Promise<AuditLogsResponse> {
    const params = new URLSearchParams();

    if (filters?.event_type) {
      params.append("event_type", filters.event_type);
    }
    if (filters?.actor_id) {
      params.append("actor_id", filters.actor_id);
    }
    if (filters?.start_date) {
      params.append("start_date", filters.start_date);
    }
    if (filters?.end_date) {
      params.append("end_date", filters.end_date);
    }
    if (filters?.page) {
      params.append("page", String(filters.page));
    }
    if (filters?.limit) {
      params.append("limit", String(filters.limit));
    }

    const queryString = params.toString();
    const url = `${AUDIT_BASE_URL}/audits${queryString ? `?${queryString}` : ""}`;

    try {
      const response = await apiClient.get<AuditLogsResponse | AuditLog[]>(url);
      const raw = response.data;
      // Handle both old (plain array) and new (paginated object) response shapes
      if (Array.isArray(raw)) {
        return { data: raw, total: raw.length, page: filters?.page ?? 1, limit: filters?.limit ?? raw.length };
      }
      return raw;
    } catch (error) {
      console.error("[Audit Service] Error fetching audit logs:", error);
      throw error;
    }
  },

  /**
   * Fetch a specific audit log by ID
   */
  async getAuditLogById(id: string): Promise<AuditLog> {
    const response = await apiClient.get<AuditLog>(
      `${AUDIT_BASE_URL}/audits/${id}`,
    );
    return response.data;
  },

  /**
   * Fetch audit logs for a specific actor
   */
  async getAuditLogsByActor(actorId: string): Promise<AuditLogsResponse> {
    return this.getAuditLogs({ actor_id: actorId });
  },

  /**
   * Fetch audit logs by event type
   */
  async getAuditLogsByEventType(eventType: string): Promise<AuditLogsResponse> {
    return this.getAuditLogs({ event_type: eventType });
  },
};
