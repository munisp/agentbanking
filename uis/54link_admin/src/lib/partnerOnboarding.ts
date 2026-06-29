export type OperatorRole = "branch" | "operations" | "treasury" | "compliance";
export type PartnerType = "mfb" | "fintech" | "cooperative" | "agency" | "enterprise";
export type PartnerPlan = "starter" | "growth" | "enterprise";
export type PartnerStage =
  | "draft"
  | "submitted"
  | "compliance_review"
  | "commercial_review"
  | "operations_review"
  | "approved"
  | "provisioning"
  | "launch_ready"
  | "launched";
export type ApprovalStage = "compliance_review" | "commercial_review" | "operations_review" | "launch_signoff";
export type ApprovalState = "pending" | "approved" | "rejected";

export interface PartnerChecklistItem {
  key: string;
  label: string;
  owner: "partner" | "compliance" | "operations";
  completed: boolean;
}

export interface PartnerContact {
  name: string;
  role: string;
  email: string;
  phone: string;
}

export interface PartnerCommercialProfile {
  plan: PartnerPlan;
  billingModel: string;
  revenueSharePct: number;
  settlementBank: string;
  settlementAccountName: string;
  settlementAccountNumber: string;
  settlementFrequency: "daily" | "weekly" | "monthly";
  goLiveTarget?: string;
}

export interface PartnerComplianceProfile {
  kybStatus: "not_started" | "in_review" | "approved" | "rejected";
  requiredDocumentCount: number;
  submittedDocumentCount: number;
  riskRating: "low" | "medium" | "high";
  notes?: string;
  lastReviewedAt?: string;
}

export interface PartnerBrandingProfile {
  displayName: string;
  supportEmail: string;
  primaryColor: string;
  accentColor: string;
  logoUrl: string;
  loginHeadline: string;
  customDomain?: string;
}

export interface PartnerOnboardingRecord {
  id: string;
  tenantId: string;
  partnerName: string;
  legalEntity: string;
  partnerType: PartnerType;
  region: string;
  stage: PartnerStage;
  requestedModules: string[];
  primaryContact: PartnerContact;
  operationsContact: PartnerContact;
  commercial: PartnerCommercialProfile;
  compliance: PartnerComplianceProfile;
  branding: PartnerBrandingProfile;
  checklist: PartnerChecklistItem[];
  blockers: string[];
  readinessScore: number;
  createdAt: string;
  updatedAt: string;
  submittedAt?: string;
  launchedAt?: string;
  lastSubmittedBy?: string;
}

export interface PartnerApprovalRecord {
  id: string;
  partnerId: string;
  stage: ApprovalStage;
  title: string;
  detail: string;
  state: ApprovalState;
  requiredRole: OperatorRole;
  requestedAt: string;
  requestedById: string;
  resolvedAt?: string;
  resolutionNote?: string;
}

interface RequestOptions extends RequestInit {
  role?: OperatorRole;
  actorId?: string;
  query?: Record<string, string | number | boolean | undefined>;
}

function buildUrl(path: string, query?: RequestOptions["query"]) {
  const url = new URL(`/api/platform${path}`, window.location.origin);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  headers.set("Content-Type", "application/json");
  if (options.role) headers.set("x-operator-role", options.role);
  if (options.actorId) headers.set("x-actor-id", options.actorId);

  const response = await fetch(buildUrl(path, options.query), {
    ...options,
    headers,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function getPartnerOnboardingRecords() {
  return requestJson<{ asOf: string; items: PartnerOnboardingRecord[]; total: number; approvals: PartnerApprovalRecord[] }>("/partner-onboarding");
}

export async function getPartnerOnboardingRecord(partnerId: string) {
  return requestJson<{ partner: PartnerOnboardingRecord; approvals: PartnerApprovalRecord[] }>(`/partner-onboarding/${partnerId}`);
}

export async function createPartnerOnboardingDraft(payload: Partial<PartnerOnboardingRecord>, role: OperatorRole = "operations", actorId = "operations.default") {
  return requestJson<{ partner: PartnerOnboardingRecord; approvals: PartnerApprovalRecord[] }>("/partner-onboarding", {
    method: "POST",
    body: JSON.stringify(payload),
    role,
    actorId,
  });
}

export async function updatePartnerOnboardingDraft(partnerId: string, payload: Partial<PartnerOnboardingRecord>, role: OperatorRole = "operations", actorId = "operations.default") {
  return requestJson<{ partner: PartnerOnboardingRecord; approvals: PartnerApprovalRecord[] }>(`/partner-onboarding/${partnerId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
    role,
    actorId,
  });
}

export async function submitPartnerOnboarding(partnerId: string, role: OperatorRole = "operations", actorId = "partner.portal") {
  return requestJson<{ partner: PartnerOnboardingRecord; approvals: PartnerApprovalRecord[] }>(`/partner-onboarding/${partnerId}/submit`, {
    method: "POST",
    body: JSON.stringify({}),
    role,
    actorId,
  });
}

export async function approvePartnerOnboardingApproval(partnerId: string, approvalId: string, resolutionNote = "Approved in onboarding console.", role: OperatorRole = "operations", actorId = "operations.default") {
  return requestJson<{ partner: PartnerOnboardingRecord; approval: PartnerApprovalRecord; approvals: PartnerApprovalRecord[] }>(`/partner-onboarding/${partnerId}/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ resolutionNote }),
    role,
    actorId,
  });
}

export async function rejectPartnerOnboardingApproval(partnerId: string, approvalId: string, resolutionNote = "Rejected in onboarding console.", role: OperatorRole = "operations", actorId = "operations.default") {
  return requestJson<{ partner: PartnerOnboardingRecord; approval: PartnerApprovalRecord; approvals: PartnerApprovalRecord[] }>(`/partner-onboarding/${partnerId}/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ resolutionNote }),
    role,
    actorId,
  });
}
