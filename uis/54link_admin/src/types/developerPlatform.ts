// Developer Platform Types

// ============================================
// Admin Roles
// ============================================
export type AdminRole =
  | "platform_admin"
  | "app_reviewer"
  | "support_admin"
  | "finance_admin"
  | "security_admin";

// ============================================
// Developer Management
// ============================================
export type DeveloperStatus = "active" | "suspended" | "terminated";
export type KYBStatus = "not_started" | "pending" | "verified" | "rejected";

export interface Developer {
  id: string;
  email: string;
  name: string;
  organization_id: string;
  organization_name: string;
  role: "owner" | "admin" | "developer";
  status: DeveloperStatus;
  kyb_status: KYBStatus;
  total_apps: number;
  active_installations: number;
  monthly_revenue: number;
  created_at: string;
  last_login_at: string;
}

export interface DeveloperDetails extends Developer {
  apps: Array<{
    app_id: string;
    name: string;
    status: AppStatus;
    installations: number;
  }>;
  api_usage: {
    monthly_calls: number;
    rate_limit: number;
    current_tier: TierLevel;
  };
  compliance: {
    kyb_verified: boolean;
    terms_accepted: boolean;
    privacy_policy_accepted: boolean;
    last_security_review: string;
  };
}

export interface DevelopersListResponse {
  developers: Developer[];
  total: number;
  page: number;
  limit: number;
}

export interface SuspendDeveloperRequest {
  reason: string;
  notes: string;
  notify_developer: boolean;
  suspend_apps: boolean;
}

export interface ReactivateDeveloperRequest {
  reason: string;
  reactivate_apps: boolean;
}

export interface UpdateDeveloperTierRequest {
  tier: TierLevel;
  rate_limit: number;
  custom_pricing: boolean;
  reason: string;
}

// ============================================
// Organization Management
// ============================================
export type TierLevel = "free" | "starter" | "professional" | "enterprise";
export type OrgStatus = "active" | "suspended" | "terminated";

export interface Organization {
  id: string;
  name: string;
  legal_name: string;
  country: string;
  kyb_status: KYBStatus;
  tier_level: TierLevel;
  total_developers: number;
  total_apps: number;
  monthly_revenue: number;
  status: OrgStatus;
  created_at: string;
}

export interface OrganizationFullDetails extends Organization {
  registration_number: string;
  kyb_verified_at: string;
  kyb_documents: {
    cac_certificate: string;
    proof_of_address: string;
    director_id: string;
  };
  developers: Array<{
    id: string;
    name: string;
    role: string;
  }>;
  apps: Array<{
    app_id: string;
    name: string;
    status: AppStatus;
  }>;
  financial: {
    tier_level: TierLevel;
    monthly_revenue: number;
    platform_fees_ytd: number;
    payout_account: string;
    next_payout_date: string;
  };
  compliance: {
    kyb_verified: boolean;
    security_reviews_passed: number;
    last_security_scan: string;
    vulnerabilities_found: number;
  };
}

export interface OrganizationsListResponse {
  organizations: Organization[];
  total: number;
  page: number;
  limit: number;
}

export interface UpdateOrgStatusRequest {
  status: OrgStatus;
  reason: string;
  notify: boolean;
}

// ============================================
// KYB Verification
// ============================================
export interface KYBApplication {
  organization_id: string;
  organization_name: string;
  legal_name: string;
  registration_number: string;
  country: string;
  submitted_at: string;
  documents: {
    cac_certificate: "available" | "missing";
    proof_of_address: "available" | "missing";
    director_id: "available" | "missing";
  };
  priority: "high" | "normal" | "low";
  days_pending: number;
}

export interface PendingKYBResponse {
  applications: KYBApplication[];
  total: number;
  average_review_time_days: number;
}

export interface KYBReviewDetails {
  organization_id: string;
  organization_name: string;
  legal_name: string;
  registration_number: string;
  country: string;
  address: string;
  website: string;
  contact_email: string;
  contact_phone: string;
  submitted_at: string;
  documents: Array<{
    type: string;
    filename: string;
    url: string;
    uploaded_at: string;
  }>;
  verification_checks: {
    registration_number_valid: boolean | null;
    address_verified: boolean | null;
    directors_checked: boolean | null;
    aml_screening: boolean | null;
  };
  risk_score: number | null;
}

export interface ApproveKYBRequest {
  tier_level: TierLevel;
  rate_limit: number;
  notes: string;
  notify_organization: boolean;
  grant_production_access: boolean;
}

export interface RejectKYBRequest {
  reason: string;
  details: string;
  required_actions: string[];
  allow_resubmission: boolean;
  notify_organization: boolean;
}

export interface RequestDocumentsRequest {
  documents_required: string[];
  reason: string;
  deadline_days: number;
}

// ============================================
// App Review & Approval
// ============================================
export type AppStatus =
  | "draft"
  | "pending_review"
  | "in_review"
  | "published"
  | "rejected"
  | "unpublished";

export type ReviewStatus = "pending" | "in_progress" | "completed" | "failed";

export interface AppPendingReview {
  app_id: string;
  name: string;
  developer_id: string;
  developer_name: string;
  organization_name: string;
  category: string;
  version: string;
  submitted_at: string;
  days_in_review: number;
  priority: "high" | "normal" | "low";
  review_status: {
    security_scan: ReviewStatus;
    compliance_check: ReviewStatus;
    functionality_test: ReviewStatus;
    documentation_review: ReviewStatus;
  };
}

export interface PendingReviewResponse {
  apps: AppPendingReview[];
  total: number;
  average_review_time_days: number;
}

export interface AppReviewDetails {
  app_id: string;
  name: string;
  description: string;
  developer_id: string;
  organization_id: string;
  version: string;
  category: string;
  submitted_at: string;
  api_scopes: string[];
  webhook_url: string;
  redirect_uris: string[];
  screenshots: string[];
  privacy_policy_url: string;
  terms_url: string;
  review_checklist: {
    security_scan: {
      status: ReviewStatus;
      findings: number;
      severity: string;
      completed_at: string;
    };
    compliance_check: {
      status: ReviewStatus;
      gdpr_compliant: boolean;
      ndpr_compliant: boolean;
      pci_dss_required: boolean;
      pci_dss_compliant: boolean;
    };
    functionality_test: {
      status: ReviewStatus;
      test_cases: number;
      passed: number;
      failed: number;
    };
    documentation_review: {
      status: ReviewStatus;
      api_docs_quality: string | null;
      user_guide_present: boolean;
    };
  };
  risk_assessment: {
    risk_level: "low" | "medium" | "high" | "critical";
    data_sensitivity: "low" | "medium" | "high";
    requires_additional_review: boolean;
  };
}

export interface ApproveAppRequest {
  complexity_tier: "basic" | "standard" | "advanced" | "enterprise";
  featured: boolean;
  categories: string[];
  release_notes: string;
  notify_developer: boolean;
  publish_immediately: boolean;
}

export interface RejectAppRequest {
  reason: string;
  details: string;
  required_fixes: string[];
  severity: "low" | "medium" | "high" | "critical";
  allow_resubmission: boolean;
  notify_developer: boolean;
}

export interface RequestAppChangesRequest {
  changes_required: string[];
  deadline_days: number;
  priority: "high" | "normal" | "low";
}

export interface FeatureAppRequest {
  featured: boolean;
  feature_duration_days: number;
  feature_position: string;
  start_date: string;
}

export interface UnpublishAppRequest {
  reason: string;
  notify_users: boolean;
  disable_existing_installations: boolean;
  allow_developer_fix: boolean;
}

// ============================================
// Security Vetting
// ============================================
export type ScanStatus = "pending" | "running" | "completed" | "failed";
export type Severity = "critical" | "high" | "medium" | "low" | "none";

export interface SecurityScan {
  scan_id: string;
  app_id: string;
  app_name: string;
  scan_type: string;
  status: ScanStatus;
  severity: Severity;
  vulnerabilities_found: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  started_at: string;
  completed_at: string;
}

export interface SecurityScansResponse {
  scans: SecurityScan[];
  total: number;
}

export interface Vulnerability {
  id: string;
  title: string;
  severity: Severity;
  description: string;
  affected_endpoint: string;
  cwe_id: string;
  cvss_score: number;
  recommendation: string;
  status: "open" | "resolved" | "in_progress";
}

export interface ScanDetails {
  scan_id: string;
  app_id: string;
  scan_type: string;
  status: ScanStatus;
  severity: Severity;
  compliance_score: number;
  vulnerabilities: Vulnerability[];
  recommendations: string[];
  completed_at: string;
}

export interface InitiateScanRequest {
  app_id: string;
  scan_type: string;
  include_penetration_test: boolean;
  include_code_review: boolean;
  include_dependency_check: boolean;
  priority: "high" | "normal" | "low";
}

export interface UpdateVulnerabilityRequest {
  status: "open" | "resolved" | "in_progress";
  resolution: string;
  verified_by: string;
  notes: string;
}

// ============================================
// Marketplace Management
// ============================================
export interface MarketplaceStats {
  total_apps: number;
  published_apps: number;
  pending_review: number;
  featured_apps: number;
  total_installations: number;
  active_installations: number;
  total_developers: number;
  active_developers: number;
  categories: Array<{
    category: string;
    app_count: number;
    installations: number;
  }>;
  top_apps: Array<{
    app_id: string;
    name: string;
    installations: number;
    rating: number;
  }>;
  revenue: {
    monthly_gmv: number;
    platform_fees: number;
    growth_percentage: number;
  };
}

export interface AppCategory {
  id: string;
  name: string;
  description: string;
  icon: string;
  order: number;
  featured: boolean;
}

export interface UpdateCategoriesRequest {
  categories: AppCategory[];
}

export interface FeaturedApp {
  app_id: string;
  position: number;
  start_date: string;
  end_date: string;
}

export interface ManageFeaturedAppsRequest {
  featured_apps: FeaturedApp[];
}

export interface AppReview {
  review_id: string;
  app_id: string;
  app_name: string;
  user_id: string;
  rating: number;
  review_text: string;
  flags: string[];
  flag_count: number;
  created_at: string;
}

export interface FlaggedReviewsResponse {
  reviews: AppReview[];
  total: number;
}

export interface RemoveReviewRequest {
  reason: string;
  notify_user: boolean;
}

// ============================================
// Fee Configuration
// ============================================
export interface TierFee {
  platform_fee_percentage: number;
  monthly_minimum: number;
  setup_fee: number;
  annual_fee: number;
  api_calls_included: number;
  overage_per_call: number;
}

export interface TieredFee {
  min_amount: number;
  max_amount: number;
  flat_fee: number;
  percentage_fee: number;
}

export interface VolumeDiscount {
  min_monthly_volume: number;
  max_monthly_volume: number;
  discount_percent: number;
  description: string;
}

export interface FeeConfiguration {
  id: string;
  name: string;
  base_platform_fee: number;
  tier_fees: {
    [key: string]: TierFee;
  };
  transaction_fees: {
    enabled: boolean;
    fee_model: "flat" | "percentage" | "tiered";
    tiered_fees: TieredFee[];
  };
  volume_discounts: VolumeDiscount[];
  effective_from: string;
  is_active: boolean;
}

export interface CreateFeeConfigRequest {
  name: string;
  description: string;
  base_platform_fee: number;
  tier_fees: {
    [key: string]: Partial<TierFee>;
  };
  effective_from: string;
}

export interface ActivateFeeConfigRequest {
  effective_date: string;
  notify_developers: boolean;
  grace_period_days: number;
}

export interface AssignCustomFeeRequest {
  app_id: string;
  complexity_tier: string;
  negotiated_rate: number;
  custom_overrides: {
    monthly_minimum_override?: number;
    api_calls_override?: number;
  };
  approved_by: string;
  notes: string;
  effective_from: string;
}

export interface RevenueReport {
  period: string;
  total_gmv: number;
  total_platform_fees: number;
  total_transaction_fees: number;
  total_volume_discounts: number;
  net_revenue: number;
  breakdown_by_tier: Array<{
    tier: string;
    app_count: number;
    gmv: number;
    platform_fees: number;
    net_revenue: number;
  }>;
  top_revenue_apps: Array<{
    app_id: string;
    app_name: string;
    gmv: number;
    platform_fees: number;
  }>;
}

// ============================================
// Platform Analytics
// ============================================
export interface PlatformOverview {
  period: string;
  date_range: {
    start: string;
    end: string;
  };
  metrics: {
    total_api_calls: number;
    successful_calls: number;
    failed_calls: number;
    average_latency_ms: number;
    uptime_percentage: number;
    active_developers: number;
    new_developers: number;
    active_apps: number;
    new_apps: number;
    total_installations: number;
    new_installations: number;
    gmv: number;
    platform_revenue: number;
  };
  growth: {
    api_calls: number;
    developers: number;
    apps: number;
    revenue: number;
  };
  top_performers: {
    most_popular_apps: any[];
    highest_revenue_apps: any[];
    most_active_developers: any[];
  };
}

export interface APIUsageAnalytics {
  total_requests: number;
  by_environment: {
    production: number;
    sandbox: number;
  };
  by_status_code: {
    "2xx": number;
    "4xx": number;
    "5xx": number;
  };
  by_endpoint: Array<{
    endpoint: string;
    method: string;
    requests: number;
    avg_latency_ms: number;
    error_rate: number;
  }>;
  peak_usage: {
    timestamp: string;
    requests_per_minute: number;
  };
}

export interface DeveloperGrowthMetrics {
  timeline: Array<{
    date: string;
    new_registrations: number;
    total_developers: number;
  }>;
  retention: {
    "30_day": number;
    "60_day": number;
    "90_day": number;
  };
  activation_funnel: {
    registered: number;
    kyb_submitted: number;
    kyb_verified: number;
    app_submitted: number;
    app_published: number;
  };
}

// ============================================
// Tenant App Management
// ============================================
export interface TenantInstallation {
  installation_id: string;
  app_id: string;
  app_name: string;
  tenant_id: string;
  tenant_name: string;
  status: "active" | "inactive" | "suspended";
  installed_at: string;
  last_accessed: string;
  api_calls_30d: number;
}

export interface TenantInstallationsResponse {
  installations: TenantInstallation[];
  total: number;
}

export interface SuspendInstallationRequest {
  reason: string;
  notify_tenant: boolean;
  notify_developer: boolean;
}

export interface InstallationDetails {
  installation_id: string;
  app_id: string;
  tenant_id: string;
  status: "active" | "inactive" | "suspended";
  configuration: {
    api_key: string;
    webhook_url: string;
  };
  permissions_granted: string[];
  usage_stats: {
    api_calls_total: number;
    api_calls_30d: number;
    last_accessed: string;
  };
  installed_at: string;
}

// ============================================
// System Configuration
// ============================================
export interface PlatformSettings {
  app_review_enabled: boolean;
  auto_approval_for_updates: boolean;
  require_kyb_for_production: boolean;
  default_rate_limit: number;
  max_apps_per_developer: number;
  sandbox_data_retention_days: number;
  enable_featured_apps: boolean;
  marketplace_enabled: boolean;
}

export interface SystemHealth {
  status: "healthy" | "degraded" | "unhealthy";
  services: {
    database: "healthy" | "degraded" | "unhealthy";
    redis: "healthy" | "degraded" | "unhealthy";
    apisix: "healthy" | "degraded" | "unhealthy";
    storage: "healthy" | "degraded" | "unhealthy";
  };
  metrics: {
    uptime_seconds: number;
    cpu_usage_percent: number;
    memory_usage_percent: number;
    disk_usage_percent: number;
  };
  last_deployment: string;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  admin_id: string;
  admin_name: string;
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, any>;
  ip_address: string;
}

export interface AuditLogsResponse {
  logs: AuditLog[];
  total: number;
  page: number;
}

// ============================================
// Emergency & Bulk Operations
// ============================================
export interface EmergencySuspendAppRequest {
  app_id: string;
  reason: string;
  disable_all_installations: boolean;
  notify_all_stakeholders: boolean;
  priority: "critical" | "high";
}

export interface BulkSuspendDevelopersRequest {
  developer_ids: string[];
  reason: string;
  notify: boolean;
}

// ============================================
// Generic API Response
// ============================================
export interface ApiResponse {
  message: string;
  [key: string]: unknown;
}
