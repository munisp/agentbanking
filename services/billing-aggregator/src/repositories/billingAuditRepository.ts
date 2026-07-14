import { AppDataSource } from "../database/dataSource";
import { BillingAuditLogEntity } from "../entity/BillingAuditLogEntity";
import { BillingAuditAction } from "../utils/enums";

export interface RecordAuditInput {
  tenant_id: string;
  user_id: string;
  user_name?: string;
  action: BillingAuditAction;
  resource_type?: string;
  resource_id?: string;
  before_state?: Record<string, unknown>;
  after_state?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  ip_address?: string;
  user_agent?: string;
  session_id?: string;
}

class BillingAuditRepository {
  private manager = AppDataSource.manager;

  async record(input: RecordAuditInput): Promise<BillingAuditLogEntity> {
    const entry = this.manager.create(BillingAuditLogEntity, {
      ...input,
      notification_sent: false,
    });

    const saved = await this.manager.save(entry);

    const notifiable_actions: BillingAuditAction[] = [
      BillingAuditAction.CONFIG_CREATED,
      BillingAuditAction.CONFIG_UPDATED,
      BillingAuditAction.CONFIG_DELETED,
      BillingAuditAction.BILLING_MODEL_CHANGED,
      BillingAuditAction.TENANT_BILLING_PROVISIONED,
    ];

    if (notifiable_actions.includes(input.action)) {
      const kafkaUrl = process.env.KAFKA_BROKER_URL;
      if (kafkaUrl) {
        console.log(`[BillingAudit] Kafka publish: billing.audit.${input.action}`, {
          audit_id: saved.id,
          tenant_id: input.tenant_id,
          action: input.action,
        });
      }
    }

    return saved;
  }

  async query(input: {
    tenant_id: string;
    action?: BillingAuditAction;
    user_id?: string;
    resource_type?: string;
    start_date?: Date;
    end_date?: Date;
    limit?: number;
    offset?: number;
  }) {
    const limit = input.limit ?? 50;
    const offset = input.offset ?? 0;

    const qb = this.manager
      .createQueryBuilder(BillingAuditLogEntity, "log")
      .where("log.tenant_id = :tenant_id", { tenant_id: input.tenant_id });

    if (input.action) qb.andWhere("log.action = :action", { action: input.action });
    if (input.user_id) qb.andWhere("log.user_id = :user_id", { user_id: input.user_id });
    if (input.resource_type)
      qb.andWhere("log.resource_type = :resource_type", { resource_type: input.resource_type });
    if (input.start_date)
      qb.andWhere("log.created_at >= :start_date", { start_date: input.start_date });
    if (input.end_date)
      qb.andWhere("log.created_at <= :end_date", { end_date: input.end_date });

    qb.orderBy("log.created_at", "DESC").skip(offset).take(limit);

    const [logs, total] = await qb.getManyAndCount();
    return { logs, total, limit, offset };
  }

  async getSummary(tenant_id: string, days: number) {
    const since = new Date(Date.now() - days * 86400000);

    const qb = this.manager
      .createQueryBuilder(BillingAuditLogEntity, "log")
      .where("log.tenant_id = :tenant_id", { tenant_id })
      .andWhere("log.created_at >= :since", { since });

    const total = await qb.getCount();

    const action_counts = await this.manager
      .createQueryBuilder(BillingAuditLogEntity, "log")
      .select("log.action", "action")
      .addSelect("COUNT(*)", "count")
      .where("log.tenant_id = :tenant_id", { tenant_id })
      .andWhere("log.created_at >= :since", { since })
      .groupBy("log.action")
      .getRawMany();

    const recent_changes = await this.manager.find(BillingAuditLogEntity, {
      where: { tenant_id },
      order: { created_at: "DESC" },
      take: 10,
    });

    return {
      total_events: total,
      by_action: action_counts.map((a) => ({ action: a.action, count: Number(a.count) })),
      recent_changes,
      period_days: days,
    };
  }

  async getResourceHistory(tenant_id: string, resource_type: string, resource_id: string) {
    const history = await this.manager.find(BillingAuditLogEntity, {
      where: { tenant_id, resource_type, resource_id },
      order: { created_at: "DESC" },
    });
    return { history, total: history.length };
  }

  async queryForExport(tenant_id: string, start_date: Date, end_date: Date) {
    return this.manager.find(BillingAuditLogEntity, {
      where: { tenant_id },
      order: { created_at: "DESC" },
    });
  }
}

export const billingAuditRepository = new BillingAuditRepository();
