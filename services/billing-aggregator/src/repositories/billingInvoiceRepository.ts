import { AppDataSource } from "../database/dataSource";
import { BillingInvoiceEntity } from "../entity/BillingInvoiceEntity";
import { InvoiceStatus } from "../utils/enums";

export class BillingInvoiceRepository {
  private entity = BillingInvoiceEntity;
  private manager = AppDataSource.manager;

  async create(input: {
    tenant_id: string;
    invoice_number: string;
    plan?: string;
    period_start: Date;
    period_end: Date;
    subtotal: number;
    tax_rate: number;
    tax_amount: number;
    total: number;
    currency: string;
    due_date: Date;
    line_items: unknown[];
  }) {
    const invoice = new this.entity();
    Object.assign(invoice, input);
    return await this.manager.save(invoice);
  }

  async findByTenant(tenant_id: string, limit = 100) {
    return await this.manager.find(this.entity, {
      where: { tenant_id },
      order: { due_date: "DESC" },
      take: limit,
    });
  }

  async findAll(limit = 100) {
    return await this.manager.find(this.entity, {
      order: { due_date: "DESC" },
      take: limit,
    });
  }

  async markPaid(invoice_number: string, payment_ref: string, paid_at?: Date) {
    const invoice = await this.manager.findOne(this.entity, { where: { invoice_number } });
    if (!invoice) return null;

    invoice.status = InvoiceStatus.PAID;
    invoice.payment_ref = payment_ref;
    invoice.paid_at = paid_at ?? new Date();

    return await this.manager.save(invoice);
  }
}

export const billingInvoiceRepository = new BillingInvoiceRepository();

export function toInvoiceDto(invoice: BillingInvoiceEntity) {
  return {
    invoiceNumber: invoice.invoice_number,
    tenantId: invoice.tenant_id,
    plan: invoice.plan,
    totalAmount: invoice.total,
    currency: invoice.currency,
    status: invoice.status,
    dueAt: invoice.due_date,
    paidAt: invoice.paid_at ?? null,
    generatedAt: invoice.created_at,
  };
}
