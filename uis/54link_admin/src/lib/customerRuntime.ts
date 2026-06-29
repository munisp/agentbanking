// Design philosophy: restored original banking PWA shell.
// This runtime layer gives the recovered customer experience durable, session-like behavior in static mode.
// It stores the active customer, transfer drafts, beneficiary selections, card controls, saved billers,
// bill payments, statement rows, and notifications in localStorage so the recovered shell behaves like a working product.

import type { AuditEntry, AuthContextResponse, CustomerRecord, WorkflowCase } from "@/lib/platform";

const STORAGE_KEYS = {
  activeCustomerId: "54link-dev.customer.active-id",
  transferDraft: "54link-dev.customer.transfer-draft",
  beneficiaries: "54link-dev.customer.beneficiaries",
  transfers: "54link-dev.customer.transfers",
  billPayments: "54link-dev.customer.bill-payments",
  notifications: "54link-dev.customer.notifications",
  cards: "54link-dev.customer.cards",
  cardEvents: "54link-dev.customer.card-events",
  savedBillers: "54link-dev.customer.saved-billers",
} as const;

export interface CustomerTransferDraft {
  transferType: "bank" | "wallet" | "workflow";
  beneficiaryId: string;
  workflowId: string;
  amount: string;
  narration: string;
}

export interface CustomerBeneficiary {
  id: string;
  customerId: string;
  name: string;
  phone: string;
  location: string;
  addedAt: string;
  source: "customer" | "manual" | "workflow";
}

export interface CustomerTransferRecord {
  id: string;
  customerId: string;
  beneficiaryId?: string;
  beneficiaryName: string;
  amount: number;
  narration: string;
  transferType: CustomerTransferDraft["transferType"];
  status: "prepared" | "submitted" | "completed";
  createdAt: string;
}

export interface CustomerBillPaymentRecord {
  id: string;
  customerId: string;
  category: "electricity" | "water" | "internet" | "school" | "airtime";
  provider: string;
  amount: number;
  status: "scheduled" | "paid" | "pending";
  paidAt: string;
  reference: string;
  billerId?: string;
  customerReference?: string;
  customerName?: string;
  scheduledFor?: string;
  evidenceStatus?: "verified" | "ready" | "scheduled";
  channel?: "self-service" | "saved-biller" | "operator-assisted";
}

export interface CustomerStatementRecord {
  id: string;
  customerId: string;
  title: string;
  detail: string;
  amount: number;
  direction: "credit" | "debit";
  type: "transfer" | "bill_payment" | "workflow" | "deposit";
  status: "completed" | "pending" | "prepared";
  timestamp: string;
  reference?: string;
  category?: string;
}

export interface CustomerNotification {
  id: string;
  customerId: string;
  title: string;
  message: string;
  type: "info" | "success" | "warning" | "error";
  read: boolean;
  createdAt: string;
  actionUrl?: string;
}

export interface CustomerCardProfile {
  id: string;
  customerId: string;
  type: "virtual" | "physical";
  brand: "visa" | "mastercard";
  lastFour: string;
  expiryDate: string;
  cardHolder: string;
  balance: number;
  isLocked: boolean;
  controls: {
    online: boolean;
    atm: boolean;
    international: boolean;
  };
  spendingLimits: {
    daily: number;
    atm: number;
    online: number;
  };
  colorTone: "blue" | "graphite";
  updatedAt: string;
}

export interface CustomerCardEvent {
  id: string;
  cardId: string;
  customerId: string;
  title: string;
  detail: string;
  severity: "info" | "warning" | "success";
  createdAt: string;
}

export interface CustomerSavedBiller {
  id: string;
  customerId: string;
  category: CustomerBillPaymentRecord["category"];
  provider: string;
  billerId: string;
  customerReference: string;
  nickname: string;
  lastAmount: number;
  verifiedName?: string;
  lastPaidAt?: string;
  createdAt: string;
}

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readJson<T>(key: string, fallback: T): T {
  if (!canUseStorage()) return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson<T>(key: string, value: T) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

export function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function isoOffset(hours: number) {
  return new Date(Date.now() + hours * 3600_000).toISOString();
}

export function getActiveCustomerId(customers: CustomerRecord[]) {
  const persisted = readJson<string | null>(STORAGE_KEYS.activeCustomerId, null);
  return persisted && customers.some((customer) => customer.id === persisted) ? persisted : customers[0]?.id ?? null;
}

export function setActiveCustomerId(customerId: string) {
  writeJson(STORAGE_KEYS.activeCustomerId, customerId);
}

export function getTransferDraft(): CustomerTransferDraft {
  return readJson<CustomerTransferDraft>(STORAGE_KEYS.transferDraft, {
    transferType: "bank",
    beneficiaryId: "",
    workflowId: "",
    amount: "",
    narration: "",
  });
}

export function setTransferDraft(draft: CustomerTransferDraft) {
  writeJson(STORAGE_KEYS.transferDraft, draft);
}

export function clearTransferDraft() {
  setTransferDraft({
    transferType: "bank",
    beneficiaryId: "",
    workflowId: "",
    amount: "",
    narration: "",
  });
}

export function getBeneficiaries(_customers: CustomerRecord[], _workflows: WorkflowCase[]) {
  const stored = readJson<CustomerBeneficiary[]>(STORAGE_KEYS.beneficiaries, []);
  if (stored.length) return stored;

  const empty: CustomerBeneficiary[] = [];
  writeJson(STORAGE_KEYS.beneficiaries, empty);
  return empty;
}

export function upsertBeneficiary(beneficiary: CustomerBeneficiary) {
  const current = readJson<CustomerBeneficiary[]>(STORAGE_KEYS.beneficiaries, []);
  const next = [beneficiary, ...current.filter((item) => item.id !== beneficiary.id)].slice(0, 20);
  writeJson(STORAGE_KEYS.beneficiaries, next);
  return next;
}

export function getTransfers(_customers: CustomerRecord[], _workflows: WorkflowCase[]) {
  const stored = readJson<CustomerTransferRecord[]>(STORAGE_KEYS.transfers, []);
  if (stored.length) return stored;

  const empty: CustomerTransferRecord[] = [];
  writeJson(STORAGE_KEYS.transfers, empty);
  return empty;
}

export function addTransferRecord(record: CustomerTransferRecord) {
  const current = readJson<CustomerTransferRecord[]>(STORAGE_KEYS.transfers, []);
  const next = [record, ...current].slice(0, 50);
  writeJson(STORAGE_KEYS.transfers, next);
  return next;
}

function defaultCards(_customers: CustomerRecord[]) {
  return [] satisfies CustomerCardProfile[];
}

export function getCustomerCards(customers: CustomerRecord[]) {
  const stored = readJson<CustomerCardProfile[]>(STORAGE_KEYS.cards, []);
  if (stored.length) return stored;
  const defaults = defaultCards(customers);
  writeJson(STORAGE_KEYS.cards, defaults);
  return defaults;
}

export function updateCustomerCard(card: CustomerCardProfile) {
  const current = readJson<CustomerCardProfile[]>(STORAGE_KEYS.cards, []);
  const next = [
    { ...card, updatedAt: new Date().toISOString() },
    ...current.filter((item) => item.id !== card.id),
  ].slice(0, 12);
  writeJson(STORAGE_KEYS.cards, next);
  return next;
}

function defaultCardEvents(cards: CustomerCardProfile[], audits: AuditEntry[]) {
  if (!cards.length) {
    return [] satisfies CustomerCardEvent[];
  }

  return audits.slice(0, 4).map((audit, index) => ({
    id: `card-audit-${audit.id}`,
    cardId: cards[index % cards.length].id,
    customerId: cards[index % cards.length].customerId,
    title: audit.outcome,
    detail: audit.detail || `${audit.entityType.replaceAll("_", " ")} updated on the control rail.`,
    severity: audit.severity === "critical" ? "warning" : audit.severity === "warning" ? "warning" : "info",
    createdAt: audit.timestamp,
  })) satisfies CustomerCardEvent[];
}

export function getCardEvents(cards: CustomerCardProfile[], audits: AuditEntry[]) {
  const stored = readJson<CustomerCardEvent[]>(STORAGE_KEYS.cardEvents, []);
  if (stored.length) return stored;
  const defaults = defaultCardEvents(cards, audits);
  writeJson(STORAGE_KEYS.cardEvents, defaults);
  return defaults;
}

export function addCardEvent(event: CustomerCardEvent) {
  const current = readJson<CustomerCardEvent[]>(STORAGE_KEYS.cardEvents, []);
  const next = [event, ...current].slice(0, 50);
  writeJson(STORAGE_KEYS.cardEvents, next);
  return next;
}

function defaultSavedBillers(_activeCustomer: CustomerRecord | null) {
  return [] satisfies CustomerSavedBiller[];
}

export function getSavedBillers(activeCustomer: CustomerRecord | null) {
  const stored = readJson<CustomerSavedBiller[]>(STORAGE_KEYS.savedBillers, []);
  if (stored.length) return stored;
  const defaults = defaultSavedBillers(activeCustomer);
  writeJson(STORAGE_KEYS.savedBillers, defaults);
  return defaults;
}

export function upsertSavedBiller(record: CustomerSavedBiller) {
  const current = readJson<CustomerSavedBiller[]>(STORAGE_KEYS.savedBillers, []);
  const next = [record, ...current.filter((item) => item.id !== record.id)].slice(0, 20);
  writeJson(STORAGE_KEYS.savedBillers, next);
  return next;
}

export function removeSavedBiller(id: string) {
  const current = readJson<CustomerSavedBiller[]>(STORAGE_KEYS.savedBillers, []);
  const next = current.filter((item) => item.id !== id);
  writeJson(STORAGE_KEYS.savedBillers, next);
  return next;
}

export function getBillPayments(_activeCustomer: CustomerRecord | null) {
  const stored = readJson<CustomerBillPaymentRecord[]>(STORAGE_KEYS.billPayments, []);
  if (stored.length) return stored;

  const empty: CustomerBillPaymentRecord[] = [];
  writeJson(STORAGE_KEYS.billPayments, empty);
  return empty;
}

export function addBillPayment(record: CustomerBillPaymentRecord) {
  const current = readJson<CustomerBillPaymentRecord[]>(STORAGE_KEYS.billPayments, []);
  const next = [record, ...current].slice(0, 30);
  writeJson(STORAGE_KEYS.billPayments, next);
  return next;
}

export function getNotifications(activeCustomer: CustomerRecord | null, audits: AuditEntry[]) {
  const stored = readJson<CustomerNotification[]>(STORAGE_KEYS.notifications, []);
  if (stored.length) return stored;

  const customerId = activeCustomer?.id ?? "CUS-001";
  const defaults: CustomerNotification[] = audits.slice(0, 4).map((audit, index) => ({
    id: `notification-${audit.id}`,
    customerId,
    title: index === 0 ? "Transfer rail update" : audit.outcome,
    message: audit.detail || `${audit.entityType.replaceAll("_", " ")} updated on the restored banking shell.`,
    type: index === 0 ? "warning" : index === 1 ? "success" : "info",
    read: index > 1,
    createdAt: audit.timestamp,
    actionUrl: index === 0 ? "/customer/transfers" : "/control-center",
  }));

  writeJson(STORAGE_KEYS.notifications, defaults);
  return defaults;
}

export function setNotifications(notifications: CustomerNotification[]) {
  writeJson(STORAGE_KEYS.notifications, notifications.slice(0, 50));
}

export function getStatements(activeCustomer: CustomerRecord | null, transfers: CustomerTransferRecord[], bills: CustomerBillPaymentRecord[], workflows: WorkflowCase[]) {
  const customerId = activeCustomer?.id ?? "CUS-001";

  const transferRows: CustomerStatementRecord[] = transfers
    .filter((transfer) => transfer.customerId === customerId)
    .map((transfer) => ({
      id: `statement-${transfer.id}`,
      customerId,
      title: transfer.beneficiaryName,
      detail: transfer.narration || "Transfer instruction",
      amount: transfer.amount,
      direction: "debit",
      type: "transfer",
      status: transfer.status === "completed" ? "completed" : transfer.status === "submitted" ? "pending" : "prepared",
      timestamp: transfer.createdAt,
      reference: transfer.id,
      category: transfer.transferType,
    }));

  const billRows: CustomerStatementRecord[] = bills
    .filter((bill) => bill.customerId === customerId)
    .map((bill) => ({
      id: `statement-${bill.id}`,
      customerId,
      title: bill.provider,
      detail: `${bill.category.replace("_", " ")} bill payment${bill.customerReference ? ` · ${bill.customerReference}` : ""}`,
      amount: bill.amount,
      direction: "debit",
      type: "bill_payment",
      status: bill.status === "paid" ? "completed" : bill.status === "scheduled" ? "prepared" : "pending",
      timestamp: bill.scheduledFor ?? bill.paidAt,
      reference: bill.reference,
      category: bill.category,
    }));

  const workflowRows: CustomerStatementRecord[] = workflows.slice(0, 2).map((workflow, index) => ({
    id: `statement-workflow-${workflow.id}`,
    customerId,
    title: workflow.product,
    detail: `${workflow.stage} · ${workflow.status}`,
    amount: Math.max(25000, Math.round(workflow.amount * 0.03) || 35000),
    direction: index === 0 ? "credit" : "debit",
    type: "workflow",
    status: "completed",
    timestamp: new Date(Date.now() - (index + 2) * 86400_000).toISOString(),
    reference: workflow.id,
    category: workflow.channel,
  }));

  return [...transferRows, ...billRows, ...workflowRows].sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime());
}

export function exportStatementsCsv(rows: CustomerStatementRecord[]) {
  const header = ["timestamp", "title", "detail", "amount", "direction", "type", "status", "reference", "category"];
  const body = rows.map((row) => [
    row.timestamp,
    row.title,
    row.detail,
    String(row.amount),
    row.direction,
    row.type,
    row.status,
    row.reference ?? "",
    row.category ?? "",
  ]);

  return [header, ...body]
    .map((line) => line.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");
}

export function buildSessionSummary(customers: CustomerRecord[], authContext: AuthContextResponse | null) {
  const activeCustomerId = getActiveCustomerId(customers);
  const activeCustomer = customers.find((customer) => customer.id === activeCustomerId) ?? customers[0] ?? null;
  const visibleName = activeCustomer?.name ?? authContext?.actorId ?? "54link-dev Customer";

  return {
    activeCustomer,
    activeCustomerId,
    visibleName,
  };
}
