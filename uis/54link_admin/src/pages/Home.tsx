import { useEffect, useMemo, useState } from "react";
import { Link } from "wouter";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Filter,
  Landmark,
  Leaf,
  Plus,
  Scale,
  Search,
  ShieldCheck,
  Sparkles,
  Waves,
  Warehouse,
  Workflow,
} from "lucide-react";

import {
  advanceWorkflowCase,
  createCustomer,
  createExportJob,
  deleteCustomer,
  formatCurrency,
  formatRelativeIso,
  getAuditEntries,
  getAuthContext,
  getCustomers,
  getERPNextOverview,
  getExportJobs,
  getIslamicBankingOverview,
  getLedgerSyncOverview,
  getOperatorActions,
  getPlatformOverview,
  getRoleProfiles,
  getTellerOverview,
  getTigerBeetleIntegration,
  getWorkflowCases,
  searchPlatform,
  updateCustomer,
  updateOperatorActionStatus,
  type AuditEntry,
  type AuthContextResponse,
  type CustomerRecord,
  type ERPNextResponse,
  type ExportJob,
  type HealthStatus,
  type IslamicBankingResponse,
  type OperatorAction,
  type OperatorRole,
  type OverviewResponse,
  type ReconciliationResponse,
  type RoleProfile,
  type SearchRecord,
  type TellerOverviewResponse,
  type TigerBeetleIntegrationResponse,
  type WorkflowCase,
} from "@/lib/platform";

// Design philosophy: Editorial agrarian modernism integrated into a production-shaped core banking workbench.
// Every restored domain should feel embedded in the original banking surface rather than bolted on as a detached microsite.
const rolePanels = [
  {
    title: "Field onboarding desk",
    detail:
      "Assisted KYC, geography capture, and farmer-season intake stay visible beside the approval queue rather than living in a disconnected wizard.",
    icon: Leaf,
  },
  {
    title: "Risk and compliance lane",
    detail:
      "CDD refresh, evidence review, dispute investigation, and workflow escalations remain operator-visible inside the same core banking surface.",
    icon: ShieldCheck,
  },
  {
    title: "Treasury and settlement lane",
    detail:
      "Trade finance, teller balancing, ERP synchronization, and ledger parity checks stay connected to customers, workflows, and service posture.",
    icon: Warehouse,
  },
] as const;

const quickActions = [
  {
    label: "Create customer profile",
    requiredPermission: "customer.write",
    allowedRoles: ["branch", "operations"] as OperatorRole[],
    route: "/control-center#customer-create",
    supportText: "Branch and operations teams can create and service customer records from the core shell.",
  },
  {
    label: "Advance KYC review",
    requiredPermission: "workflow.advance",
    allowedRoles: ["branch", "operations"] as OperatorRole[],
    route: "/control-center#workflow-cases",
    supportText: "Workflow progression remains limited to the frontline and central operations personas.",
  },
  {
    label: "Escalate trade exception",
    requiredPermission: "trade.approve",
    allowedRoles: ["treasury"] as OperatorRole[],
    route: "/trade-finance",
    supportText: "Treasury retains the trade-exception escalation rail while other personas receive read-only visibility.",
  },
  {
    label: "Review dispute evidence",
    requiredPermission: "dispute.manage",
    allowedRoles: ["operations", "compliance"] as OperatorRole[],
    route: "/disputes",
    supportText: "Dispute evidence review stays attached to operations and compliance roles inside the shared workbench.",
  },
] as const;

const exportScopeDomainMap: Partial<Record<string, string[]>> = {
  customers: ["customer-operations"],
  workflows: ["customer-operations", "trade-finance", "dispute-management"],
  actions: ["customer-operations", "trade-finance", "dispute-management", "erpnext-sync"],
  disputes: ["dispute-management"],
  "trade-finance": ["trade-finance"],
  ledger: ["ledger-reconciliation"],
  reconciliation: ["ledger-reconciliation"],
  insurance: ["agricultural-insurance"],
  compliance: ["agricultural-insurance", "dispute-management", "islamic-banking"],
  audit: ["ledger-reconciliation", "dispute-management", "agricultural-insurance", "islamic-banking"],
  "teller-sessions": ["teller-operations"],
};

const domainIcons: Record<string, typeof Landmark> = {
  "customer-operations": Landmark,
  "teller-operations": Workflow,
  "islamic-banking": ShieldCheck,
  "trade-finance": BarChart3,
  "agricultural-insurance": Leaf,
  "dispute-management": Scale,
  "erpnext-sync": Sparkles,
  "ledger-reconciliation": Warehouse,
};

type ActivityRecord = {
  id: string;
  actor: string;
  action: string;
  entity: string;
  time: string;
};

type GovernanceAlert = {
  id: string;
  title: string;
  detail: string;
  severity: string;
  owner: string;
  area: string;
};

type BenchmarkSignal = {
  label: string;
  benchmark: string;
  value: string;
  changeLabel: string;
  coverageLabel: string;
};

const defaultCustomerSegments = ["Agriculture", "Trade", "SME", "Retail"] as const;
const defaultCustomerTiers = ["Tier 1", "Tier 2", "Tier 3"] as const;

function statusTone(status: HealthStatus | OperatorAction["status"] | CustomerRecord["status"]) {
  switch (status) {
    case "healthy":
    case "Done":
    case "Active":
      return "border-emerald-400/35 bg-emerald-500/10 text-emerald-200";
    case "degraded":
    case "Pending":
      return "border-amber-300/35 bg-amber-300/10 text-amber-100";
    case "down":
    case "Review":
    case "In progress":
      return "border-rose-400/35 bg-rose-500/10 text-rose-100";
    default:
      return "border-white/15 bg-white/5 text-stone-100";
  }
}

function formatCount(value: number, singular: string, plural = `${singular}s`) {
  return `${value} ${value === 1 ? singular : plural}`;
}

export default function Home() {
  const [customers, setCustomers] = useState<CustomerRecord[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [workflowCases, setWorkflowCases] = useState<WorkflowCase[]>([]);
  const [activityFeed, setActivityFeed] = useState<ActivityRecord[]>([]);
  const [operatorActions, setOperatorActions] = useState<OperatorAction[]>([]);
  const [selectedDomain, setSelectedDomain] = useState<string>("trade-finance");
  const [searchQuery, setSearchQuery] = useState("");
  const [unifiedResults, setUnifiedResults] = useState<SearchRecord[]>([]);
  const [segmentFilter, setSegmentFilter] = useState<string>("All");
  const [statusFilter, setStatusFilter] = useState<string>("All");
  const [activeRole, setActiveRole] = useState<OperatorRole>("operations");
  const [roleProfiles, setRoleProfiles] = useState<RoleProfile[]>([]);
  const [authContext, setAuthContext] = useState<AuthContextResponse | null>(null);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [exportJobs, setExportJobs] = useState<ExportJob[]>([]);
  const [tigerBeetleIntegration, setTigerBeetleIntegration] = useState<TigerBeetleIntegrationResponse | null>(null);
  const [platformOverview, setPlatformOverview] = useState<OverviewResponse | null>(null);
  const [tellerOverview, setTellerOverview] = useState<TellerOverviewResponse | null>(null);
  const [ledgerOverview, setLedgerOverview] = useState<ReconciliationResponse | null>(null);
  const [erpnextOverview, setErpnextOverview] = useState<ERPNextResponse | null>(null);
  const [islamicOverview, setIslamicOverview] = useState<IslamicBankingResponse | null>(null);
  const [platformLoading, setPlatformLoading] = useState(true);
  const [platformError, setPlatformError] = useState<string | null>(null);
  const [newCustomer, setNewCustomer] = useState({
    name: "",
    segment: "Agriculture",
    tier: "Tier 1",
    location: "",
    relationshipManager: "",
    risk: "Medium",
    status: "Pending",
    bvn: "",
    phone: "",
    balance: "0",
  });

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const [overview, teller, ledger, erpnext, islamic, customerResponse, workflowResponse, actionResponse, rolesResponse, authResponse, auditResponse, exportResponse, tigerBeetleResponse] = await Promise.all([
          getPlatformOverview(activeRole),
          getTellerOverview(),
          getLedgerSyncOverview(),
          getERPNextOverview(),
          getIslamicBankingOverview(),
          getCustomers(undefined, activeRole),
          getWorkflowCases(),
          getOperatorActions(undefined, activeRole),
          getRoleProfiles(),
          getAuthContext(activeRole),
          getAuditEntries(activeRole),
          getExportJobs(activeRole),
          getTigerBeetleIntegration(),
        ]);

        if (!active) {
          return;
        }

        setPlatformOverview(overview);
        setTellerOverview(teller);
        setLedgerOverview(ledger);
        setErpnextOverview(erpnext);
        setIslamicOverview(islamic);
        setCustomers(customerResponse.items);
        setWorkflowCases(workflowResponse.items);
        setOperatorActions(actionResponse.items);
        setRoleProfiles(rolesResponse.items);
        setAuthContext(authResponse);
        setAuditEntries(auditResponse.items);
        setActivityFeed(
          auditResponse.items.slice(0, 6).map((entry) => ({
            id: entry.id,
            actor: `${entry.actorRole} · ${entry.actorId}`,
            action: entry.action.replaceAll("_", " "),
            entity: `${entry.entityType} · ${entry.outcome}`,
            time: formatRelativeIso(entry.timestamp),
          })),
        );
        setExportJobs(exportResponse.items);
        setTigerBeetleIntegration(tigerBeetleResponse);
        setPlatformError(null);
      } catch (issue) {
        if (!active) {
          return;
        }

        setPlatformError(issue instanceof Error ? issue.message : "Unable to load integrated platform data");
      } finally {
        if (active) {
          setPlatformLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [activeRole]);

  useEffect(() => {
    let active = true;

    if (!searchQuery.trim()) {
      setUnifiedResults([]);
      return () => {
        active = false;
      };
    }

    void (async () => {
      try {
        const response = await searchPlatform(searchQuery.trim());
        if (active) {
          setUnifiedResults(response.items);
        }
      } catch {
        if (active) {
          setUnifiedResults([]);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [searchQuery]);

  const filteredCustomers = useMemo(() => {
    return customers.filter((customer) => {
      const matchesQuery =
        !searchQuery.trim() ||
        [customer.name, customer.id, customer.location, customer.relationshipManager, customer.phone, customer.bvn]
          .join(" ")
          .toLowerCase()
          .includes(searchQuery.toLowerCase());
      const matchesSegment = segmentFilter === "All" || customer.segment === segmentFilter;
      const matchesStatus = statusFilter === "All" || customer.status === statusFilter;
      return matchesQuery && matchesSegment && matchesStatus;
    });
  }, [customers, searchQuery, segmentFilter, statusFilter]);

  const selectedCustomer = useMemo(() => {
    return filteredCustomers.find((customer) => customer.id === selectedCustomerId) ?? filteredCustomers[0] ?? null;
  }, [filteredCustomers, selectedCustomerId]);

  const highlightedCase = useMemo(() => {
    return [...workflowCases].sort((a, b) => a.slaHours - b.slaHours)[0] ?? workflowCases[0];
  }, [workflowCases]);

  const platformProducts = useMemo(() => {
    const products = platformOverview?.products ?? [];
    if (!authContext?.visibleDomains?.length) {
      return products;
    }
    return products.filter((product) => authContext.visibleDomains.includes(product.key) || product.key === "customer-operations");
  }, [authContext, platformOverview]);

  const availableSegments = useMemo(() => {
    const values = new Set<string>([...defaultCustomerSegments, newCustomer.segment]);
    customers.forEach((customer) => {
      if (customer.segment) {
        values.add(customer.segment);
      }
    });
    return Array.from(values).sort((left, right) => left.localeCompare(right));
  }, [customers, newCustomer.segment]);

  const availableTiers = useMemo(() => {
    const values = new Set<string>([...defaultCustomerTiers, newCustomer.tier]);
    customers.forEach((customer) => {
      if (customer.tier) {
        values.add(customer.tier);
      }
    });
    return Array.from(values).sort((left, right) => left.localeCompare(right));
  }, [customers, newCustomer.tier]);

  const operationalAlerts = useMemo<GovernanceAlert[]>(() => {
    const serviceAlerts = (platformOverview?.serviceHealth ?? [])
      .filter((service) => service.status !== "healthy")
      .map((service) => ({
        id: `service-${service.name}`,
        title: `${service.name} requires attention`,
        detail: service.description,
        severity: service.status === "down" ? "critical" : "warning",
        owner: "Platform control",
        area: service.route,
      }));

    const actionAlerts = operatorActions
      .filter((action) => action.status !== "Done")
      .slice(0, 3)
      .map((action) => ({
        id: action.id,
        title: action.title,
        detail: action.detail,
        severity: action.status === "Pending" ? "warning" : "critical",
        owner: action.owner,
        area: action.domainKey,
      }));

    const alerts = [...serviceAlerts, ...actionAlerts].slice(0, 4);
    if (alerts.length > 0) {
      return alerts;
    }

    return [
      {
        id: "runtime-posture",
        title: "Runtime posture healthy",
        detail: "Live operator actions, workflow queues, and service surfaces are loading without fallback alert cards.",
        severity: "info",
        owner: "Platform control",
        area: "operations",
      },
      {
        id: "workflow-coverage",
        title: "Workflow coverage available",
        detail: `${workflowCases.length} workflow cases and ${operatorActions.length} operator actions are currently available from the active runtime.`,
        severity: "info",
        owner: "Operations desk",
        area: "customer-operations",
      },
    ];
  }, [operatorActions, platformOverview, workflowCases.length]);

  const benchmarkSignals = useMemo<BenchmarkSignal[]>(() => {
    const serviceSignals = (platformOverview?.serviceHealth ?? []).slice(0, 4).map((service) => ({
      label: service.name,
      benchmark: service.description,
      value: service.latencyMs !== undefined ? `${service.latencyMs} ms` : service.status,
      changeLabel: service.status === "healthy" ? "Healthy posture" : `${service.status} posture`,
      coverageLabel: `${service.dependencies.length} dependencies`,
    }));

    if (serviceSignals.length > 0) {
      return serviceSignals;
    }

    const openActions = operatorActions.filter((action) => action.status !== "Done").length;
    return [
      {
        label: "Customer operations",
        benchmark: "Fallback view now summarizes current runtime counts when upstream service telemetry is unavailable.",
        value: `${customers.length} customers`,
        changeLabel: `${workflowCases.length} workflows in queue`,
        coverageLabel: `${openActions} open actions`,
      },
      {
        label: "Governance exports",
        benchmark: "Operational export posture is derived from the active runtime rather than fallback commodity benchmark records.",
        value: `${exportJobs.filter((job) => job.status === "Ready").length} ready`,
        changeLabel: `${exportJobs.filter((job) => job.status === "Queued").length} queued`,
        coverageLabel: `${auditEntries.length} audit entries`,
      },
    ];
  }, [auditEntries.length, customers.length, exportJobs, operatorActions, platformOverview, workflowCases.length]);

  const integratedMetrics = useMemo(() => {
    if (platformOverview?.metrics?.length) {
      return platformOverview.metrics;
    }

    const openActions = operatorActions.filter((action) => action.status !== "Done").length;
    const readyExports = exportJobs.filter((job) => job.status === "Ready").length;
    const healthyServices = (platformOverview?.serviceHealth ?? []).filter((service) => service.status === "healthy").length;

    return [
      {
        label: "Customers",
        value: customers.length.toString(),
        detail: `${workflowCases.length} workflows in queue`,
        trend: customers.length > 0 ? "up" : "flat",
      },
      {
        label: "Open actions",
        value: openActions.toString(),
        detail: `${exportJobs.filter((job) => job.status === "Queued").length} exports queued`,
        trend: openActions === 0 ? "up" : "flat",
      },
      {
        label: "Visible modules",
        value: platformProducts.length.toString(),
        detail: `${healthyServices} healthy services`,
        trend: healthyServices > 0 ? "up" : "flat",
      },
      {
        label: "Ready exports",
        value: readyExports.toString(),
        detail: `${auditEntries.length} audit entries loaded`,
        trend: readyExports > 0 ? "up" : "flat",
      },
    ];
  }, [auditEntries.length, customers.length, exportJobs, operatorActions, platformOverview, platformProducts.length, workflowCases.length]);

  const integratedDomainCards = useMemo(() => {
    return platformProducts.map((product) => {
      if (product.key === "teller-operations") {
        const openSessions = tellerOverview?.sessions.filter((session) => session.state !== "closed").length ?? 0;
        const pendingTransactions = tellerOverview?.recentTransactions.filter((tx) => tx.status !== "posted").length ?? 0;
        return {
          ...product,
          signal: `${formatCount(openSessions, "open session")} · ${formatCount(pendingTransactions, "pending posting")}`,
          accent: "Embedded teller balancing and branch cash posture now sit beside customer operations in the same surface.",
        };
      }

      if (product.key === "islamic-banking") {
        const activeContracts = islamicOverview?.summary.activeContracts ?? 0;
        const outstandingExposure = islamicOverview?.summary.outstandingExposure ?? 0;
        return {
          ...product,
          signal: `${formatCount(activeContracts, "active contract")} · ${formatCurrency(outstandingExposure)}`,
          accent: "Murabaha, Ijara, and Mudarabah monitoring are visible as first-class core banking modules instead of separate product silos.",
        };
      }

      if (product.key === "erpnext-sync") {
        const retrying = erpnextOverview?.syncHistory.filter((item) => item.status === "retrying" || item.status === "failed").length ?? 0;
        const mappedDocuments = erpnextOverview?.config.mappedDocuments.length ?? 0;
        return {
          ...product,
          signal: `${formatCount(mappedDocuments, "mapped document")} · ${formatCount(retrying, "sync at risk", "syncs at risk")}`,
          accent: "Accounting sync health is now part of the core operator picture rather than a hidden integration sidebar.",
        };
      }

      if (product.key === "ledger-reconciliation") {
        const discrepancies = ledgerOverview?.discrepancies.length ?? 0;
        const snapshotState = ledgerOverview?.latestSnapshot?.state ?? "unknown";
        return {
          ...product,
          signal: `${formatCount(discrepancies, "variance")} · ${snapshotState} parity posture`,
          accent: "TigerBeetle and PostgreSQL repair posture is embedded into day-to-day banking operations so exceptions stay visible.",
        };
      }

      if (product.key === "trade-finance" || product.key === "agricultural-insurance" || product.key === "dispute-management") {
        const openActions = operatorActions.filter((action) => action.domainKey === product.key && action.status !== "Done").length;
        return {
          ...product,
          signal: `${formatCount(openActions, "open action")} · ${product.services[0] ?? "service-backed"}`,
          accent: "This domain is embedded into the same customer, workflow, and governance frame as the rest of core banking.",
        };
      }

      return {
        ...product,
        signal: `${product.services.length} shared services · ${product.status} posture`,
        accent: "Customer operations remain the coordinating surface for the wider banking stack.",
      };
    });
  }, [erpnextOverview, islamicOverview, ledgerOverview, operatorActions, platformProducts, tellerOverview]);

  const selectedDomainCard = useMemo(() => {
    return integratedDomainCards.find((product) => product.key === selectedDomain) ?? integratedDomainCards[0] ?? null;
  }, [integratedDomainCards, selectedDomain]);

  const selectedDomainActions = useMemo(() => {
    if (!selectedDomainCard) {
      return operatorActions;
    }

    return operatorActions.filter((action) => action.domainKey === selectedDomainCard.key);
  }, [operatorActions, selectedDomainCard]);

  const selectedDomainDetails = useMemo(() => {
    if (!selectedDomainCard) {
      return [];
    }

    switch (selectedDomainCard.key) {

      case "teller-operations":
        return [
          {
            label: "Open sessions",
            value: String(tellerOverview?.sessions.filter((session) => session.state !== "closed").length ?? 0),
            detail: "Branch and till sessions visible from the core banking rail.",
          },
          {
            label: "Pending transactions",
            value: String(tellerOverview?.recentTransactions.filter((tx) => tx.status !== "posted").length ?? 0),
            detail: "Transactions awaiting posting or review remain operator-visible.",
          },
          {
            label: "Last balanced",
            value: formatRelativeIso(tellerOverview?.sessions[0]?.lastBalancedAt),
            detail: "Most recent teller balancing signal pulled into the core workbench.",
          },
        ];
      case "islamic-banking":
        return [
          {
            label: "Active contracts",
            value: String(islamicOverview?.summary.activeContracts ?? 0),
            detail: "Contract visibility across Murabaha, Ijara, and Mudarabah products.",
          },
          {
            label: "Outstanding exposure",
            value: formatCurrency(islamicOverview?.summary.outstandingExposure ?? 0),
            detail: "Portfolio exposure remains visible beside the rest of core banking.",
          },
          {
            label: "Takaful coverage",
            value: `${islamicOverview?.summary.takafulCoverageRate ?? 0}%`,
            detail: "Protection posture remains visible without leaving the main workflow surface.",
          },
        ];
      case "erpnext-sync":
        return [
          {
            label: "Integration mode",
            value: erpnextOverview?.config.mode ?? "unknown",
            detail: "Configuration posture is kept close to operator workflows.",
          },
          {
            label: "Mapped documents",
            value: String(erpnextOverview?.config.mappedDocuments.length ?? 0),
            detail: "Document coverage is visible without a separate integration console.",
          },
          {
            label: "Sync backlog",
            value: String(erpnextOverview?.syncHistory.filter((item) => item.status !== "succeeded").length ?? 0),
            detail: "Queued, retrying, and failed sync items stay inside the core workbench.",
          },
        ];
      case "ledger-reconciliation":
        return [
          {
            label: "Snapshot state",
            value: ledgerOverview?.latestSnapshot?.state ?? "unknown",
            detail: "TigerBeetle to PostgreSQL parity posture remains operator-visible.",
          },
          {
            label: "Discrepancies",
            value: String(ledgerOverview?.discrepancies.length ?? 0),
            detail: "Open repair items are embedded into the same control surface.",
          },
          {
            label: "Manual reviews",
            value: String(ledgerOverview?.latestSnapshot?.manualReviewCount ?? 0),
            detail: "Review workload stays tied to other operational queues.",
          },
        ];
      default:
        return [
          {
            label: "Shared services",
            value: String(selectedDomainCard.services.length),
            detail: "Service dependencies remain visible alongside the domain.",
          },
          {
            label: "Open actions",
            value: String(selectedDomainActions.filter((action) => action.status !== "Done").length),
            detail: "Actionable follow-up stays attached to the domain inside core banking.",
          },
          {
            label: "Status posture",
            value: selectedDomainCard.status,
            detail: "Degraded conditions stay visible instead of disappearing behind route boundaries.",
          },
        ];
    }
  }, [erpnextOverview, islamicOverview, ledgerOverview, selectedDomainActions, selectedDomainCard, tellerOverview]);

  const selectedLedgerOutcome = useMemo(() => {
    if (!selectedDomainCard) {
      return null;
    }

    switch (selectedDomainCard.key) {
      case "teller-operations":
        return tellerOverview?.ledgerOutcome ?? null;
      case "islamic-banking":
        return islamicOverview?.ledgerOutcome ?? null;
      case "erpnext-sync":
        return erpnextOverview?.ledgerOutcome ?? null;
      case "ledger-reconciliation":
        return ledgerOverview?.ledgerOutcome ?? null;
      default:
        return null;
    }
  }, [erpnextOverview, islamicOverview, ledgerOverview, selectedDomainCard, tellerOverview]);

  useEffect(() => {
    if (platformProducts.length && !platformProducts.some((product) => product.key === selectedDomain)) {
      setSelectedDomain(platformProducts[0]?.key ?? "customer-operations");
    }
  }, [platformProducts, selectedDomain]);

  useEffect(() => {
    if (!filteredCustomers.length) {
      if (selectedCustomerId) {
        setSelectedCustomerId("");
      }
      return;
    }

    if (!filteredCustomers.some((customer) => customer.id === selectedCustomerId)) {
      setSelectedCustomerId(filteredCustomers[0]?.id ?? "");
    }
  }, [filteredCustomers, selectedCustomerId]);

  const middlewareHighlights = useMemo(() => {
    return (tigerBeetleIntegration?.middleware ?? []).slice(0, 6);
  }, [tigerBeetleIntegration]);

  const middlewareEndpointCards = useMemo(() => {
    const config = tigerBeetleIntegration?.config ?? {};

    return [
      {
        key: "tigerbeetle",
        title: "TigerBeetle cluster",
        value: config.tigerbeetle?.addresses ?? "Unavailable",
        detail: config.tigerbeetle?.clusterId ? `Cluster ${config.tigerbeetle.clusterId}` : "Ledger authority endpoint not visible.",
      },
      {
        key: "kafka",
        title: "Kafka brokers",
        value: config.kafka?.brokers ?? "Unavailable",
        detail: "Event fan-out path for posting and reconciliation outcomes.",
      },
      {
        key: "temporal",
        title: "Temporal frontend",
        value: config.temporal?.hostPort ?? "Unavailable",
        detail: "Workflow orchestration endpoint for long-running operational flows.",
      },
      {
        key: "keycloak",
        title: "Keycloak issuer",
        value: config.keycloak?.issuer ?? authContext?.issuer ?? "Unavailable",
        detail: "Identity context that shapes visible domains and operator personas.",
      },
      {
        key: "permify",
        title: "Permify endpoint",
        value: config.permify?.endpoint ?? authContext?.authzEndpoint ?? "Unavailable",
        detail: "Authorization check path used for role and permission enforcement.",
      },
      {
        key: "redis",
        title: "Redis cache",
        value: config.redis?.url ?? "Unavailable",
        detail: "Cache and idempotency support layer adjacent to operational workflows.",
      },
      {
        key: "apisix",
        title: "APISIX gateway",
        value: config.apisix?.publicGatewayUrl ?? "Unavailable",
        detail: "Primary ingress path for platform-facing middleware traffic.",
      },
      {
        key: "dapr",
        title: "Dapr sidecar",
        value: config.dapr?.httpPort ? `http://dapr-sidecar:${config.dapr.httpPort}` : "Unavailable",
        detail: "Service invocation sidecar used where domain adapters still depend on Dapr.",
      },
      {
        key: "postgres",
        title: "Postgres mirror",
        value: config.postgres?.url ?? "Unavailable",
        detail: "Relational mirror and reconciliation read-model destination.",
      },
      {
        key: "lakehouse",
        title: "Lakehouse query",
        value: config.lakehouse?.endpoint ?? "Unavailable",
        detail: "Downstream analytical surface for retained reporting and parity evidence.",
      },
    ].slice(0, 8);
  }, [authContext, tigerBeetleIntegration]);

  const visibleAuditEntries = useMemo(() => {
    return auditEntries.slice(0, 4);
  }, [auditEntries]);

  const visibleExportJobs = useMemo(() => {
    return exportJobs.slice(0, 4);
  }, [exportJobs]);

  const middlewareReportHistory = useMemo(() => {
    const auditHistory = visibleAuditEntries.slice(0, 3).map((entry) => ({
      id: `audit-${entry.id}`,
      title: entry.action.replace(/_/g, " "),
      route: entry.route,
      detail: entry.middleware.join(" · "),
      timestamp: entry.timestamp,
      type: "Audit event",
    }));
    const exportHistory = visibleExportJobs.slice(0, 3).map((job) => ({
      id: `export-${job.id}`,
      title: job.title,
      route: job.route,
      detail: `${job.format.toUpperCase()} · ${job.rowCount} rows · ${job.approvalState}`,
      timestamp: job.createdAt,
      type: "Export package",
    }));

    return [...auditHistory, ...exportHistory]
      .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime())
      .slice(0, 5);
  }, [visibleAuditEntries, visibleExportJobs]);

  const allowedDomainKeys = authContext?.visibleDomains ?? [];
  const activePermissions = authContext?.permissions ?? [];
  const activeExportScopes = authContext?.exportScopes ?? [];

  const canAdvanceWorkflow = activePermissions.includes("workflow.advance");
  const canManageDisputes = activePermissions.includes("dispute.manage");

  const canOperateSelectedDomain = selectedDomainCard
    ? !allowedDomainKeys.length || allowedDomainKeys.includes(selectedDomainCard.key)
    : false;

  const canExportSelectedDomain = selectedDomainCard
    ? activeExportScopes.some((scope) => exportScopeDomainMap[scope]?.includes(selectedDomainCard.key))
    : false;

  const roleAwareQuickActions = quickActions.map((action) => {
    const permitted = activePermissions.includes(action.requiredPermission) && action.allowedRoles.includes(activeRole);
    return {
      ...action,
      permitted,
    };
  });

  const activeRoleProfile = useMemo(() => {
    return roleProfiles.find((profile) => profile.role === activeRole) ?? null;
  }, [activeRole, roleProfiles]);

  const addActivity = (actor: string, action: string, entity: string) => {
    const now = new Date();
    setActivityFeed((current) => [
      {
        id: `ACT-${now.getTime()}`,
        actor,
        action,
        entity,
        time: now.toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" }),
      },
      ...current,
    ]);
  };

  const resetCustomerDraft = () => {
    setNewCustomer({
      name: "",
      segment: "Agriculture",
      tier: "Tier 1",
      location: "",
      relationshipManager: "",
      risk: "Medium",
      status: "Pending",
      bvn: "",
      phone: "",
      balance: "0",
    });
  };

  const addCustomer = async () => {
    if (!newCustomer.name.trim() || !newCustomer.location.trim() || !newCustomer.relationshipManager.trim()) {
      return;
    }

    try {
      const createdCustomer = await createCustomer(
        {
          name: newCustomer.name.trim(),
          segment: newCustomer.segment as CustomerRecord["segment"],
          tier: newCustomer.tier as CustomerRecord["tier"],
          location: newCustomer.location.trim(),
          relationshipManager: newCustomer.relationshipManager.trim(),
          risk: newCustomer.risk as CustomerRecord["risk"],
          status: newCustomer.status as CustomerRecord["status"],
          bvn: newCustomer.bvn.trim() || "Pending capture",
          phone: newCustomer.phone.trim() || "Pending capture",
          balance: Number(newCustomer.balance || 0),
        },
        activeRole,
      );
      setCustomers((current) => [createdCustomer, ...current.filter((item) => item.id !== createdCustomer.id)]);
      setSelectedCustomerId(createdCustomer.id);
      addActivity("Customer ops", "Created customer record", createdCustomer.name);
      resetCustomerDraft();
    } catch (issue) {
      setPlatformError(issue instanceof Error ? issue.message : "Unable to create customer record");
    }
  };

  const loadSelectedCustomerIntoForm = () => {
    if (!selectedCustomer) {
      return;
    }

    setNewCustomer({
      name: selectedCustomer.name,
      segment: selectedCustomer.segment,
      tier: selectedCustomer.tier,
      location: selectedCustomer.location,
      relationshipManager: selectedCustomer.relationshipManager,
      risk: selectedCustomer.risk,
      status: selectedCustomer.status,
      bvn: selectedCustomer.bvn,
      phone: selectedCustomer.phone,
      balance: String(selectedCustomer.balance),
    });
  };

  const saveSelectedCustomerEdits = async () => {
    if (!selectedCustomer) {
      return;
    }

    try {
      const updated = await updateCustomer(
        selectedCustomer.id,
        {
          name: newCustomer.name.trim(),
          segment: newCustomer.segment as CustomerRecord["segment"],
          tier: newCustomer.tier as CustomerRecord["tier"],
          location: newCustomer.location.trim(),
          relationshipManager: newCustomer.relationshipManager.trim(),
          risk: newCustomer.risk as CustomerRecord["risk"],
          status: newCustomer.status as CustomerRecord["status"],
          bvn: newCustomer.bvn.trim() || "Pending capture",
          phone: newCustomer.phone.trim() || "Pending capture",
          balance: Number(newCustomer.balance || 0),
        },
        activeRole,
      );
      setCustomers((current) => current.map((customer) => (customer.id === updated.id ? updated : customer)));
      setSelectedCustomerId(updated.id);
      addActivity("Customer ops", "Updated customer profile", updated.name);
      resetCustomerDraft();
    } catch (issue) {
      setPlatformError(issue instanceof Error ? issue.message : "Unable to save customer edits");
    }
  };

  const removeSelectedCustomer = async () => {
    if (!selectedCustomer) {
      return;
    }

    try {
      await deleteCustomer(selectedCustomer.id, activeRole);
      setCustomers((current) => current.filter((customer) => customer.id !== selectedCustomer.id));
      addActivity("Customer ops", "Removed customer record", selectedCustomer.name);
      resetCustomerDraft();
    } catch (issue) {
      setPlatformError(issue instanceof Error ? issue.message : "Unable to remove customer record");
    }
  };

  const advanceCase = async (caseId: string) => {
    try {
      const updated = await advanceWorkflowCase(caseId, activeRole);
      setWorkflowCases((current) => current.map((item) => (item.id === caseId ? updated : item)));
      addActivity("Workflow engine", `Advanced ${updated.id} to ${updated.stage}`, updated.customer);
    } catch (issue) {
      setPlatformError(issue instanceof Error ? issue.message : "Unable to advance workflow case");
    }
  };

  const cycleActionState = async (actionId: string) => {
    if (!canAdvanceWorkflow) {
      setPlatformError("The active role does not have permission to advance workflow actions from the core shell.");
      return;
    }

    const currentAction = operatorActions.find((action) => action.id === actionId);
    if (!currentAction) {
      return;
    }

    const nextStatus = currentAction.status === "Pending" ? "In progress" : currentAction.status === "In progress" ? "Done" : "Done";

    try {
      const updated = await updateOperatorActionStatus(actionId, nextStatus, activeRole);
      setOperatorActions((current) => current.map((action) => (action.id === actionId ? updated : action)));
      addActivity(updated.owner, `${updated.status} workflow action`, updated.title);
    } catch (issue) {
      setPlatformError(issue instanceof Error ? issue.message : "Unable to update operator action");
    }
  };

  const cycleCustomerStatus = async (customerId: string) => {
    const currentCustomer = customers.find((customer) => customer.id === customerId);
    if (!currentCustomer) {
      return;
    }
    const nextStatus: CustomerRecord["status"] =
      currentCustomer.status === "Pending"
        ? "Review"
        : currentCustomer.status === "Review"
          ? "Active"
          : currentCustomer.status === "Active"
            ? "Dormant"
            : "Active";

    try {
      const updated = await updateCustomer(customerId, { status: nextStatus }, activeRole);
      setCustomers((current) => current.map((customer) => (customer.id === customerId ? updated : customer)));
      addActivity("Customer ops", `Moved ${updated.name} to ${updated.status}`, updated.id);
    } catch (issue) {
      setPlatformError(issue instanceof Error ? issue.message : "Unable to update customer status");
    }
  };

  const queueExport = async () => {
    if (!selectedDomainCard) {
      return;
    }

    if (!canExportSelectedDomain) {
      setPlatformError("The active role cannot generate exports for the currently selected banking domain.");
      return;
    }

    try {
      const created = await createExportJob(
        {
          domainKey: selectedDomainCard.key,
          title: `${selectedDomainCard.title} operational export`,
          format: selectedDomainCard.key === "ledger-reconciliation" ? "csv" : "json",
          route: selectedDomainCard.route,
        },
        activeRole,
      );
      setExportJobs((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      addActivity(activeRoleProfile?.title ?? "Operator", "Generated export", created.title);
    } catch (issue) {
      setPlatformError(issue instanceof Error ? issue.message : "Unable to create export job");
    }
  };

  return (
    <main className="min-h-screen bg-stone-950 text-stone-100">
      <section className="border-b border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(217,119,6,0.22),_transparent_28%),linear-gradient(180deg,#111827_0%,#0c0a09_100%)]">
        <div className="container grid gap-8 px-6 py-12 lg:grid-cols-[1.2fr_0.8fr] lg:py-16">
          <div className="space-y-7">
            <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">54link-dev core banking workbench</p>
            <div className="space-y-5">
              <h1 className="max-w-4xl font-serif text-4xl leading-tight text-stone-50 sm:text-5xl lg:text-6xl">
                The original core banking surface now carries <span className="text-amber-300">teller, ERPNext, Islamic banking, trade, disputes, insurance,</span> and ledger control in one operating frame.
              </h1>
              <p className="max-w-3xl text-base leading-8 text-stone-300 sm:text-lg">
                Instead of splitting restored domains into detached destinations, the primary banking workbench now embeds their status, action queues, and service-backed signals directly into the original customer and workflow experience.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <a href="#embedded-domains" className="inline-flex items-center gap-2 rounded-full bg-amber-300 px-5 py-3 text-sm font-semibold text-stone-950 transition hover:bg-amber-200">
                Open integrated modules <ArrowRight size={16} />
              </a>
              <a href="#customer-registry" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-stone-100 transition hover:border-amber-300/60 hover:text-amber-200">
                Review customer registry <ChevronRight size={16} />
              </a>
              <button
                type="button"
                onClick={queueExport}
                disabled={!canExportSelectedDomain}
                className={`inline-flex items-center gap-2 rounded-full border px-5 py-3 text-sm font-semibold transition ${
                  canExportSelectedDomain
                    ? "border-emerald-400/35 bg-emerald-500/10 text-emerald-100 hover:border-emerald-300/60 hover:bg-emerald-500/20"
                    : "cursor-not-allowed border-white/10 bg-white/[0.03] text-stone-500"
                }`}
              >
                Queue export pack <ClipboardList size={16} />
              </button>
            </div>
            <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5 backdrop-blur">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-stone-500">Role-aware operating posture</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">Switch the core banking workbench by operational persona</h2>
                  <p className="mt-2 max-w-3xl text-sm leading-7 text-stone-300">
                    Keycloak-aligned identity context and Permify-shaped permissions now influence visible domains, action queues, and export scope in the same root banking experience.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {roleProfiles.map((profile) => (
                    <button
                      key={profile.role}
                      type="button"
                      onClick={() => setActiveRole(profile.role)}
                      className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                        activeRole === profile.role
                          ? "bg-amber-300 text-stone-950"
                          : "border border-white/10 bg-stone-950/60 text-stone-200 hover:border-amber-300/50"
                      }`}
                    >
                      {profile.title}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mt-5 grid gap-4 lg:grid-cols-3">
                <div className="rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
                  <p className="text-xs uppercase tracking-[0.28em] text-stone-500">Active role</p>
                  <h3 className="mt-2 text-lg font-semibold text-white">{activeRoleProfile?.title ?? activeRole}</h3>
                  <p className="mt-2 text-sm leading-7 text-stone-300">{activeRoleProfile?.description ?? authContext?.issuer ?? "Operational persona controls visible banking modules and workflow actions."}</p>
                </div>
                <div className="rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
                  <p className="text-xs uppercase tracking-[0.28em] text-stone-500">Identity and authorization path</p>
                  <p className="mt-2 text-sm font-semibold text-stone-100">Keycloak issuer</p>
                  <p className="mt-1 text-sm text-stone-300">{authContext?.issuer ?? "Unavailable"}</p>
                  <p className="mt-3 text-sm font-semibold text-stone-100">Permify endpoint</p>
                  <p className="mt-1 text-sm text-stone-300">{authContext?.authzEndpoint ?? "Unavailable"}</p>
                </div>
                <div className="rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
                  <p className="text-xs uppercase tracking-[0.28em] text-stone-500">Role permissions</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(authContext?.permissions ?? []).slice(0, 6).map((permission) => (
                      <span key={permission} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-200">
                        {permission}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {integratedMetrics.map((metric) => (
                <article key={metric.label} className="rounded-[1.75rem] border border-white/10 bg-white/5 p-4 backdrop-blur">
                  <p className="text-xs uppercase tracking-[0.2em] text-stone-400">{metric.label}</p>
                  <div className="mt-3 flex items-end justify-between gap-3">
                    <strong className="text-2xl font-semibold text-stone-50">{metric.value}</strong>
                    <span className={`text-sm ${metric.trend === "up" ? "text-emerald-300" : metric.trend === "down" ? "text-amber-200" : "text-stone-300"}`}>
                      {metric.trend}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-stone-300">{metric.detail}</p>
                </article>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-amber-200/15 bg-white/6 p-6 shadow-2xl shadow-black/30 backdrop-blur">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Integrated priority case</p>
                <h2 className="mt-2 text-2xl font-semibold text-white">{highlightedCase?.id ?? "No active cases"}</h2>
              </div>
              {highlightedCase ? (
                <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-amber-200">
                  {highlightedCase.slaHours}h SLA
                </span>
              ) : null}
            </div>
            {highlightedCase ? (
              <div className="mt-5 space-y-4">
                <div>
                  <p className="text-sm text-stone-400">Customer</p>
                  <p className="text-lg font-medium text-stone-100">{highlightedCase.customer}</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-sm text-stone-400">Current stage</p>
                    <p className="text-base font-medium text-stone-100">{highlightedCase.stage}</p>
                  </div>
                  <div>
                    <p className="text-sm text-stone-400">Exposure</p>
                    <p className="text-base font-medium text-stone-100">{formatCurrency(highlightedCase.amount)}</p>
                  </div>
                </div>
                <div className="rounded-[1.5rem] border border-white/10 bg-stone-950/40 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-stone-500">Next action</p>
                  <p className="mt-2 text-sm leading-7 text-stone-200">{highlightedCase.nextAction}</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {roleAwareQuickActions.map((action) => {
                    const content = (
                      <>
                        <span className="block font-medium">{action.label}</span>
                        <span className="mt-2 block text-xs leading-6 text-stone-400">{action.supportText}</span>
                      </>
                    );

                    return action.permitted ? (
                      <Link
                        key={action.label}
                        href={action.route}
                        className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-left text-sm text-stone-200 transition hover:border-amber-300/50 hover:bg-amber-300/10"
                      >
                        {content}
                      </Link>
                    ) : (
                      <button
                        key={action.label}
                        type="button"
                        disabled
                        className="cursor-not-allowed rounded-2xl border border-white/10 bg-stone-950/35 px-4 py-3 text-left text-sm text-stone-500"
                      >
                        {content}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <section className="border-b border-white/10 bg-stone-900/60">
        <div className="container grid gap-4 px-6 py-8 lg:grid-cols-3">
          {rolePanels.map((panel) => {
            const Icon = panel.icon;
            return (
              <article key={panel.title} className="rounded-[1.75rem] border border-white/10 bg-stone-900/80 p-6">
                <Icon className="text-amber-300" size={20} />
                <h3 className="mt-4 text-xl font-semibold text-white">{panel.title}</h3>
                <p className="mt-3 text-sm leading-7 text-stone-300">{panel.detail}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section id="embedded-domains" className="container space-y-8 px-6 py-14">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Embedded product surface</p>
            <h2 className="mt-2 text-3xl font-semibold text-white sm:text-4xl">Restored banking domains are now baked into core banking.</h2>
          </div>
          <p className="max-w-2xl text-sm leading-7 text-stone-300">
            The product cards below are no longer the only place these features exist. Each domain now contributes live posture, workflow actions, and service context directly inside the original banking workbench.
          </p>
        </div>

        <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-4">
          {integratedDomainCards.map((product) => {
            const Icon = domainIcons[product.key] ?? Landmark;
            const isSelected = selectedDomainCard?.key === product.key;
            return (
              <button
                key={product.key}
                type="button"
                onClick={() => setSelectedDomain(product.key)}
                className={`rounded-[1.7rem] border p-5 text-left transition ${
                  isSelected
                    ? "border-amber-300/40 bg-amber-300/10 shadow-lg shadow-amber-500/10"
                    : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-amber-300/12 text-amber-200">
                    <Icon size={20} />
                  </span>
                  <span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.24em] ${statusTone(product.status)}`}>
                    {product.status}
                  </span>
                </div>
                <h3 className="mt-5 font-serif text-3xl text-white">{product.title}</h3>
                <p className="mt-3 text-sm leading-7 text-stone-300">{product.summary}</p>
                <p className="mt-4 text-sm font-medium text-amber-100">{product.signal}</p>
                <p className="mt-3 text-sm leading-7 text-stone-400">{product.accent}</p>
              </button>
            );
          })}
        </div>

        {selectedDomainCard ? (
          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <article className="rounded-[2rem] border border-white/10 bg-stone-900/80 p-6 shadow-2xl shadow-black/20">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Integrated module detail</p>
                  <h3 className="mt-2 font-serif text-4xl text-white">{selectedDomainCard.title}</h3>
                  <p className="mt-4 max-w-2xl text-sm leading-7 text-stone-300">{selectedDomainCard.summary}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.24em] ${statusTone(selectedDomainCard.status)}`}>
                    {selectedDomainCard.status}
                  </span>
                  {canOperateSelectedDomain ? (
                    <Link href={selectedDomainCard.route} className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-stone-100 transition hover:border-amber-300/45 hover:text-amber-200">
                      Open detail route <ArrowRight size={14} />
                    </Link>
                  ) : (
                    <span className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-stone-500">
                      Route restricted for {activeRole}
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-6 grid gap-4 md:grid-cols-3">
                {selectedDomainDetails.map((detail) => (
                  <div key={detail.label} className="rounded-[1.4rem] border border-white/10 bg-stone-950/50 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-stone-500">{detail.label}</p>
                    <strong className="mt-2 block text-2xl text-white">{detail.value}</strong>
                    <p className="mt-3 text-sm leading-7 text-stone-300">{detail.detail}</p>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                {selectedDomainCard.services.map((service) => (
                  <span key={service} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-stone-300">
                    {service}
                  </span>
                ))}
              </div>

              {selectedLedgerOutcome ? (
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <div className="rounded-[1.4rem] border border-white/10 bg-stone-950/50 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-stone-500">Recommended posting seams</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedLedgerOutcome.recommendedPostingSeams.map((seam) => (
                        <span key={seam} className="rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-amber-100">
                          {seam}
                        </span>
                      ))}
                    </div>
                    <p className="mt-3 text-sm leading-7 text-stone-300">{selectedLedgerOutcome.detail}</p>
                  </div>
                  <div className="rounded-[1.4rem] border border-white/10 bg-stone-950/50 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-stone-500">Downstream sinks</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedLedgerOutcome.downstreamSinks.map((sink) => (
                        <span key={sink} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-stone-300">
                          {sink}
                        </span>
                      ))}
                    </div>
                    <p className="mt-3 text-sm leading-7 text-stone-300">TigerBeetle posting posture: {selectedLedgerOutcome.tigerBeetlePosting.replace(/_/g, " ")}.</p>
                  </div>
                </div>
              ) : null}

              <p className="mt-4 text-xs uppercase tracking-[0.22em] text-stone-500">
                Platform snapshot refreshed {formatRelativeIso(platformOverview?.asOf)}
              </p>
            </article>

            <article className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-stone-500">Operator action rail</p>
                  <h3 className="mt-2 text-2xl font-semibold text-white">Domain workflows inside the core shell</h3>
                </div>
                <ClipboardList className="text-amber-300" size={18} />
              </div>
              <div className="mt-5 space-y-3">
                {(selectedDomainActions.length ? selectedDomainActions : operatorActions).map((action) => (
                  <div key={action.id} className="rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-stone-100">{action.title}</p>
                        <p className="mt-2 text-sm leading-7 text-stone-300">{action.detail}</p>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.24em] ${statusTone(action.status)}`}>
                        {action.status}
                      </span>
                    </div>
                    <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-xs uppercase tracking-[0.2em] text-stone-500">{action.owner} · {action.due}</p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => cycleActionState(action.id)}
                          disabled={!canAdvanceWorkflow}
                          className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
                            canAdvanceWorkflow
                              ? "bg-amber-300 text-stone-950 hover:bg-amber-200"
                              : "cursor-not-allowed border border-white/10 bg-stone-950/40 text-stone-500"
                          }`}
                        >
                          {canAdvanceWorkflow
                            ? action.status === "Pending"
                              ? "Start action"
                              : action.status === "In progress"
                                ? "Mark complete"
                                : "Completed"
                            : "Workflow access restricted"}
                        </button>
                        <Link href={action.route} className="rounded-full border border-white/15 px-4 py-2 text-xs font-semibold text-stone-100 transition hover:border-amber-300/45 hover:text-amber-200">
                          Open route
                        </Link>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </div>
        ) : null}
      </section>

      <section className="container grid gap-8 px-6 py-14 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-[1.9rem] border border-white/10 bg-white/5 p-6 backdrop-blur">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-stone-500">TigerBeetle and middleware posture</p>
              <h2 className="mt-2 text-2xl font-semibold text-white">Ledger integration is robust in the financial core, but not universal across every service</h2>
              <p className="mt-2 max-w-3xl text-sm leading-7 text-stone-300">
                The workbench now surfaces the middleware chain around TigerBeetle so treasury, operations, and compliance users can see where posting, workflow, caching, authorization, and analytics intersect.
              </p>
            </div>
            <div className="rounded-[1.4rem] border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
              {tigerBeetleIntegration?.directIntegrationAssessment.summary ?? "TigerBeetle integration summary unavailable."}
            </div>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {middlewareHighlights.map((surface) => (
              <article key={surface.key} className="rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-stone-500">{surface.key}</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">{surface.title}</h3>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(surface.status)}`}>{surface.status}</span>
                </div>
                <p className="mt-3 text-sm leading-7 text-stone-300">{surface.scope}</p>
                <p className="mt-3 text-xs uppercase tracking-[0.24em] text-stone-500">Languages</p>
                <p className="mt-2 text-sm text-stone-200">{surface.languages.join(" · ")}</p>
                <p className="mt-3 text-xs uppercase tracking-[0.24em] text-stone-500">Services</p>
                <p className="mt-2 text-sm text-stone-200">{surface.services.join(", ")}</p>
              </article>
            ))}
          </div>
          <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-[1.5rem] border border-white/10 bg-stone-950/45 p-5">
              <div className="flex items-end justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-stone-500">Live default endpoints</p>
                  <h3 className="mt-2 text-lg font-semibold text-white">Middleware-facing runtime coordinates</h3>
                </div>
                <span className="rounded-full border border-white/10 px-3 py-1 text-[10px] uppercase tracking-[0.24em] text-stone-300">
                  active defaults
                </span>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {middlewareEndpointCards.map((entry) => (
                  <article key={entry.key} className="rounded-[1.25rem] border border-white/10 bg-black/20 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-stone-500">{entry.title}</p>
                    <p className="mt-2 break-all text-sm font-semibold text-stone-100">{entry.value}</p>
                    <p className="mt-3 text-sm leading-6 text-stone-300">{entry.detail}</p>
                  </article>
                ))}
              </div>
            </div>
            <div className="rounded-[1.5rem] border border-white/10 bg-stone-950/45 p-5">
              <p className="text-xs uppercase tracking-[0.24em] text-stone-500">Recent middleware-linked history</p>
              <h3 className="mt-2 text-lg font-semibold text-white">Latest evidence around endpoint-facing operations</h3>
              <div className="mt-4 space-y-3">
                {middlewareReportHistory.map((entry) => (
                  <article key={entry.id} className="rounded-[1.2rem] border border-white/10 bg-black/20 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-stone-100">{entry.title}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.2em] text-stone-500">{entry.type} · {entry.route}</p>
                      </div>
                      <span className="text-xs text-stone-400">{formatRelativeIso(entry.timestamp)}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-stone-300">{entry.detail}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="space-y-6 rounded-[1.9rem] border border-white/10 bg-stone-900/60 p-6">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-stone-500">Audit and export rail</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Role-sensitive evidence now sits beside workflow execution</h2>
          </div>
          <div className="space-y-4">
            {!canManageDisputes && activeRole === "branch" ? (
              <div className="rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4 text-sm leading-7 text-stone-300">
                Audit evidence remains visible in summary form, but deeper dispute and compliance trails stay restricted until an operations or compliance persona is active.
              </div>
            ) : null}
            {visibleAuditEntries.map((entry) => (
              <div key={entry.id} className="rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-stone-100">{entry.action.replace(/_/g, " ")}</p>
                    <p className="mt-1 text-sm text-stone-300">{entry.outcome}</p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(entry.severity === "critical" ? "down" : entry.severity === "warning" ? "degraded" : "healthy")}`}>{entry.severity}</span>
                </div>
                <p className="mt-3 text-xs uppercase tracking-[0.24em] text-stone-500">Middleware trail</p>
                <p className="mt-2 text-sm text-stone-200">{entry.middleware.join(" · ")}</p>
              </div>
            ))}
          </div>
          <div className="space-y-3 rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
            <p className="text-xs uppercase tracking-[0.24em] text-stone-500">Recent export jobs</p>
            {visibleExportJobs.map((job) => (
              <div key={job.id} className="flex items-center justify-between gap-3 border-b border-white/5 pb-3 last:border-none last:pb-0">
                <div>
                  <p className="text-sm font-semibold text-stone-100">{job.title}</p>
                  <p className="mt-1 text-xs text-stone-400">{job.format.toUpperCase()} · {job.rowCount} rows · {formatRelativeIso(job.createdAt)}</p>
                  <p className="mt-1 text-[11px] uppercase tracking-[0.22em] text-stone-500">{job.approvalState} · {job.approvalSignature}</p>
                  {(job.retainedUntil || job.reportVersion || job.approvalChain?.length || job.signedBy?.length) && (
                    <div className="mt-2 space-y-1 text-[11px] text-stone-400">
                      {job.reportVersion && <p>Version {job.reportVersion}</p>}
                      {job.retainedUntil && <p>Retained until {formatRelativeIso(job.retainedUntil)}</p>}
                      {job.approvalChain?.length ? <p>Approval chain: {job.approvalChain.join(" · ")}</p> : null}
                      {job.signedBy?.length ? <p>Signed by: {job.signedBy.join(" · ")}</p> : null}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={job.downloadUrl}
                    className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold text-stone-200 transition hover:border-amber-300/50 hover:text-white"
                  >
                    Download
                  </a>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusTone(job.status === "Failed" ? "down" : job.status === "Queued" ? "degraded" : "healthy")}`}>{job.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="operations" className="container grid gap-8 px-6 py-14 lg:grid-cols-[1.08fr_0.92fr]">
        <div className="space-y-6">
          <div className="flex flex-col gap-4 rounded-[2rem] border border-white/10 bg-stone-900/80 p-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Unified search and discovery</p>
              <h2 className="mt-2 text-3xl font-semibold text-white">Search across customers, documents, accounts, workflows, and embedded domains.</h2>
            </div>
            <div className="relative min-w-[260px] flex-1 lg:max-w-md">
              <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-stone-500" size={18} />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search Amina, WF-1182, dispute, teller, ERPNext..."
                className="w-full rounded-full border border-white/10 bg-stone-950/80 py-3 pl-11 pr-4 text-sm text-white outline-none transition focus:border-amber-300/60"
              />
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[0.92fr_1.08fr]">
            <article className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-stone-500">Search results</p>
                  <h3 className="mt-2 text-xl font-semibold text-white">Indexed operational entities</h3>
                </div>
                <Sparkles className="text-amber-300" size={18} />
              </div>
              <div className="mt-5 space-y-3">
                {unifiedResults.length ? (
                  unifiedResults.map((item) => {
                    const content = (
                      <div className="rounded-[1.4rem] border border-white/8 bg-stone-950/60 p-4 transition hover:border-amber-300/30 hover:bg-stone-950/80">
                        <div className="flex items-center justify-between gap-4">
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-amber-200/80">{item.type}</p>
                            <h4 className="mt-1 text-sm font-semibold text-stone-100">{item.title}</h4>
                          </div>
                          <ArrowRight size={16} className="text-stone-500" />
                        </div>
                        <p className="mt-2 text-sm text-stone-300">{item.subtitle}</p>
                        <p className="mt-1 text-xs text-stone-500">{item.meta}</p>
                      </div>
                    );

                    return item.route ? (
                      <Link key={item.id} href={item.route}>
                        {content}
                      </Link>
                    ) : (
                      <div key={item.id}>{content}</div>
                    );
                  })
                ) : (
                  <div className="rounded-[1.4rem] border border-dashed border-white/10 bg-stone-950/30 p-4 text-sm text-stone-400">
                    No indexed entities match the current search. Try a customer name, workflow ID, product domain, or action owner.
                  </div>
                )}
              </div>
            </article>

            <article className="rounded-[2rem] border border-white/10 bg-stone-900/80 p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-stone-500">Workflow board</p>
                  <h3 className="mt-2 text-xl font-semibold text-white">Advance customer and product cases without leaving core banking</h3>
                </div>
                <ClipboardList className="text-amber-300" size={18} />
              </div>
              <div className="mt-5 space-y-4">
                {workflowCases.map((item) => (
                  <div key={item.id} className="rounded-[1.5rem] border border-white/10 bg-stone-950/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-stone-500">{item.id}</p>
                        <h4 className="mt-1 text-base font-semibold text-white">{item.customer}</h4>
                      </div>
                      <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-amber-200">{item.stage}</span>
                    </div>
                    <div className="mt-4 grid gap-2 text-sm text-stone-300 md:grid-cols-2">
                      <p>Product: <span className="text-stone-100">{item.product}</span></p>
                      <p>Status: <span className="text-stone-100">{item.status}</span></p>
                      <p>Channel: <span className="text-stone-100">{item.channel}</span></p>
                      <p>Exposure: <span className="text-stone-100">{formatCurrency(item.amount)}</span></p>
                    </div>
                    <p className="mt-3 text-sm leading-7 text-stone-300">{item.nextAction}</p>
                    <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <span className="text-xs uppercase tracking-[0.2em] text-stone-500">{item.slaHours}h remaining</span>
                      <button
                        type="button"
                        onClick={() => advanceCase(item.id)}
                        className="inline-flex items-center justify-center gap-2 rounded-full bg-amber-300 px-4 py-2 text-xs font-semibold text-stone-950 transition hover:bg-amber-200"
                      >
                        Advance case <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </div>
        </div>

        <div className="space-y-6">
          <article className="rounded-[2rem] border border-white/10 bg-stone-900/80 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-stone-500">Alerts and governance</p>
                <h3 className="mt-2 text-xl font-semibold text-white">Priority signals from risk, compliance, and integrated platform ops</h3>
              </div>
              <AlertTriangle className="text-amber-300" size={18} />
            </div>
            <div className="mt-5 space-y-3">
              {operationalAlerts.map((alert) => (
                <div key={alert.id} className="rounded-[1.4rem] border border-white/10 bg-stone-950/40 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-stone-100">{alert.title}</p>
                      <p className="mt-2 text-sm text-stone-300">{alert.detail}</p>
                    </div>
                    <span className="rounded-full border border-white/10 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-amber-200">
                      {alert.severity}
                    </span>
                  </div>
                  <p className="mt-3 text-xs text-stone-500">{alert.owner} · {alert.area}</p>
                </div>
              ))}
            </div>
            {platformError ? <p className="mt-4 text-sm text-rose-200">{platformError}</p> : null}
            <p className="mt-4 text-xs uppercase tracking-[0.22em] text-stone-500">
              Service-backed posture refreshed {formatRelativeIso(platformOverview?.asOf)}
            </p>
          </article>

          <article className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-6">
            <p className="text-xs uppercase tracking-[0.25em] text-stone-500">Integrated signals</p>
            <h3 className="mt-2 text-xl font-semibold text-white">Live service and export signals feeding agricultural and trade decisions</h3>
            <div className="mt-5 space-y-3">
              {benchmarkSignals.map((signal) => (
                <div key={signal.label} className="grid grid-cols-[1fr_auto] gap-3 rounded-[1.25rem] border border-white/8 bg-stone-950/40 p-4 text-sm sm:grid-cols-[1fr_auto_auto]">
                  <div>
                    <p className="font-medium text-stone-100">{signal.label}</p>
                    <p className="text-stone-500">{signal.benchmark}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-stone-100">{signal.value}</p>
                    <p className="text-xs text-emerald-300">{signal.changeLabel}</p>
                  </div>
                  <div className="col-span-2 text-right text-xs text-stone-400 sm:col-span-1">{signal.coverageLabel}</div>
                </div>
              ))}
            </div>
          </article>
        </div>
      </section>

      <section id="customer-registry" className="border-y border-white/10 bg-stone-900/60">
        <div className="container grid gap-8 px-6 py-14 lg:grid-cols-[1.08fr_0.92fr]">
          <article className="rounded-[2rem] border border-white/10 bg-stone-950/60 p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Customer registry</p>
                <h2 className="mt-2 text-3xl font-semibold text-white">Filter, review, and manage customer records in the same banking surface.</h2>
              </div>
              <div className="flex flex-wrap gap-3">
                <label className="flex items-center gap-2 rounded-full border border-white/10 bg-stone-900 px-4 py-2 text-sm text-stone-300">
                  <Filter size={14} />
                  <select value={segmentFilter} onChange={(event) => setSegmentFilter(event.target.value)} className="bg-transparent outline-none">
                    <option>All</option>
                    {availableSegments.map((segment) => (
                      <option key={segment}>{segment}</option>
                    ))}
                  </select>
                </label>
                <label className="rounded-full border border-white/10 bg-stone-900 px-4 py-2 text-sm text-stone-300">
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="bg-transparent outline-none">
                    <option>All</option>
                    <option>Active</option>
                    <option>Pending</option>
                    <option>Review</option>
                    <option>Dormant</option>
                  </select>
                </label>
              </div>
            </div>

            <div className="mt-6 space-y-3 lg:hidden">
              {filteredCustomers.map((customer) => (
                <button
                  key={customer.id}
                  type="button"
                  onClick={() => setSelectedCustomerId(customer.id)}
                  className={`w-full rounded-[1.4rem] border p-4 text-left ${selectedCustomer?.id === customer.id ? "border-amber-300/35 bg-amber-300/10" : "border-white/10 bg-white/[0.04]"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-white">{customer.name}</p>
                      <p className="mt-1 text-xs text-stone-500">{customer.id} · {customer.location}</p>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em] ${statusTone(customer.status)}`}>
                      {customer.status}
                    </span>
                  </div>
                    <div className="mt-4 grid gap-2 text-sm text-stone-300">
                      <p>Segment: <span className="text-stone-100">{customer.segment}</span> · {customer.tier}</p>
                      <p>Manager: <span className="text-stone-100">{customer.relationshipManager}</span></p>
                      <p>Balance: <span className="text-stone-100">{formatCurrency(customer.balance)}</span></p>
                      <p>Risk: <span className="text-stone-100">{customer.risk}</span> · {customer.lastTouchpoint}</p>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          cycleCustomerStatus(customer.id);
                        }}
                        className="rounded-full border border-amber-300/35 px-4 py-2 text-xs font-semibold text-amber-100 transition hover:border-amber-200 hover:text-amber-50"
                      >
                        Advance status
                      </button>
                      <Link
                        href="/customer/transfers"
                        onClick={(event) => event.stopPropagation()}
                        className="rounded-full border border-white/15 px-4 py-2 text-xs font-semibold text-stone-100 transition hover:border-amber-300/45 hover:text-amber-200"
                      >
                        Open transfers
                      </Link>
                    </div>
                  </button>
              ))}
            </div>

            <div className="mt-6 hidden overflow-hidden rounded-[1.5rem] border border-white/10 lg:block">
              <div className="grid grid-cols-[1.6fr_1fr_1fr_1fr_0.8fr] gap-3 bg-white/[0.04] px-4 py-3 text-xs uppercase tracking-[0.2em] text-stone-500">
                <span>Customer</span>
                <span>Segment</span>
                <span>Manager</span>
                <span>Balance</span>
                <span>Status</span>
              </div>
              <div className="divide-y divide-white/6">
                {filteredCustomers.map((customer) => (
                  <button
                    key={customer.id}
                    type="button"
                    onClick={() => setSelectedCustomerId(customer.id)}
                    className={`grid w-full grid-cols-[1.6fr_1fr_1fr_1fr_0.8fr] gap-3 px-4 py-4 text-left text-sm text-stone-200 ${selectedCustomer?.id === customer.id ? "bg-amber-300/8" : "bg-transparent"}`}
                  >
                    <div>
                      <p className="font-medium text-white">{customer.name}</p>
                      <p className="text-xs text-stone-500">{customer.id} · {customer.location}</p>
                    </div>
                    <div>
                      <p>{customer.segment}</p>
                      <p className="text-xs text-stone-500">{customer.tier}</p>
                    </div>
                    <div>
                      <p>{customer.relationshipManager}</p>
                      <p className="text-xs text-stone-500">{customer.risk} risk</p>
                    </div>
                    <div>
                      <p>{formatCurrency(customer.balance)}</p>
                      <p className="text-xs text-stone-500">{customer.lastTouchpoint}</p>
                    </div>
                    <div className="flex flex-col items-start gap-2">
                      <span className={`rounded-full border px-3 py-1 text-xs ${statusTone(customer.status)}`}>{customer.status}</span>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          cycleCustomerStatus(customer.id);
                        }}
                        className="rounded-full border border-amber-300/35 px-3 py-1 text-[11px] font-semibold text-amber-100 transition hover:border-amber-200 hover:text-amber-50"
                      >
                        Advance status
                      </button>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </article>

          <article className="space-y-6 rounded-[2rem] border border-white/10 bg-white/[0.03] p-6">
            {selectedCustomer ? (
              <div className="rounded-[1.6rem] border border-white/10 bg-stone-950/45 p-5">
                <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Selected customer detail</p>
                <div className="mt-3 flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-2xl font-semibold text-white">{selectedCustomer.name}</h3>
                    <p className="mt-1 text-sm text-stone-400">{selectedCustomer.id} · {selectedCustomer.location}</p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs ${statusTone(selectedCustomer.status)}`}>{selectedCustomer.status}</span>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.25rem] border border-white/10 bg-black/20 p-4 text-sm text-stone-300">
                    <p>Segment: <span className="text-stone-100">{selectedCustomer.segment}</span> · {selectedCustomer.tier}</p>
                    <p className="mt-2">Relationship manager: <span className="text-stone-100">{selectedCustomer.relationshipManager}</span></p>
                    <p className="mt-2">Risk: <span className="text-stone-100">{selectedCustomer.risk}</span></p>
                  </div>
                  <div className="rounded-[1.25rem] border border-white/10 bg-black/20 p-4 text-sm text-stone-300">
                    <p>Balance: <span className="text-stone-100">{formatCurrency(selectedCustomer.balance)}</span></p>
                    <p className="mt-2">BVN: <span className="text-stone-100">{selectedCustomer.bvn}</span></p>
                    <p className="mt-2">Phone: <span className="text-stone-100">{selectedCustomer.phone}</span></p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button type="button" onClick={loadSelectedCustomerIntoForm} className="rounded-full border border-amber-300/35 px-4 py-2 text-xs font-semibold text-amber-100 transition hover:border-amber-200 hover:text-amber-50">
                    Load into edit form
                  </button>
                  <button type="button" onClick={removeSelectedCustomer} className="rounded-full border border-rose-400/35 px-4 py-2 text-xs font-semibold text-rose-100 transition hover:border-rose-300 hover:text-rose-50">
                    Remove customer
                  </button>
                  <Link href="/customer/transfers" className="rounded-full border border-white/15 px-4 py-2 text-xs font-semibold text-stone-100 transition hover:border-amber-300/45 hover:text-amber-200">
                    Open transfer lifecycle
                  </Link>
                  <Link href="/customer/statements" className="rounded-full border border-white/15 px-4 py-2 text-xs font-semibold text-stone-100 transition hover:border-amber-300/45 hover:text-amber-200">
                    Open statements
                  </Link>
                  <Link href="/customer/cards" className="rounded-full border border-white/15 px-4 py-2 text-xs font-semibold text-stone-100 transition hover:border-amber-300/45 hover:text-amber-200">
                    Open card controls
                  </Link>
                  <Link href="/customer/settings" className="rounded-full border border-white/15 px-4 py-2 text-xs font-semibold text-stone-100 transition hover:border-amber-300/45 hover:text-amber-200">
                    Open customer settings
                  </Link>
                </div>
              </div>
            ) : null}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-stone-500">Quick create</p>
                <h3 className="mt-2 text-2xl font-semibold text-white">Create a new operational customer record</h3>
              </div>
              <Plus className="text-amber-300" size={18} />
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm text-stone-300">
                <span>Name</span>
                <input value={newCustomer.name} onChange={(event) => setNewCustomer((current) => ({ ...current, name: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-white outline-none focus:border-amber-300/60" />
              </label>
              <label className="space-y-2 text-sm text-stone-300">
                <span>Location</span>
                <input value={newCustomer.location} onChange={(event) => setNewCustomer((current) => ({ ...current, location: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-white outline-none focus:border-amber-300/60" />
              </label>
              <label className="space-y-2 text-sm text-stone-300">
                <span>Relationship manager</span>
                <input value={newCustomer.relationshipManager} onChange={(event) => setNewCustomer((current) => ({ ...current, relationshipManager: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-white outline-none focus:border-amber-300/60" />
              </label>
              <label className="space-y-2 text-sm text-stone-300">
                <span>Phone</span>
                <input value={newCustomer.phone} onChange={(event) => setNewCustomer((current) => ({ ...current, phone: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-white outline-none focus:border-amber-300/60" />
              </label>
              <label className="space-y-2 text-sm text-stone-300">
                <span>Segment</span>
                <select value={newCustomer.segment} onChange={(event) => setNewCustomer((current) => ({ ...current, segment: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-white outline-none focus:border-amber-300/60">
                  {availableSegments.map((segment) => (
                    <option key={segment}>{segment}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-stone-300">
                <span>Tier</span>
                <select value={newCustomer.tier} onChange={(event) => setNewCustomer((current) => ({ ...current, tier: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-white outline-none focus:border-amber-300/60">
                  {availableTiers.map((tier) => (
                    <option key={tier}>{tier}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-stone-300">
                <span>BVN</span>
                <input value={newCustomer.bvn} onChange={(event) => setNewCustomer((current) => ({ ...current, bvn: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-white outline-none focus:border-amber-300/60" />
              </label>
              <label className="space-y-2 text-sm text-stone-300">
                <span>Starting balance</span>
                <input value={newCustomer.balance} onChange={(event) => setNewCustomer((current) => ({ ...current, balance: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-white outline-none focus:border-amber-300/60" />
              </label>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <button type="button" onClick={addCustomer} className="inline-flex items-center gap-2 rounded-full bg-amber-300 px-5 py-3 text-sm font-semibold text-stone-950 transition hover:bg-amber-200">
                Add customer record <Plus size={14} />
              </button>
              <button type="button" onClick={saveSelectedCustomerEdits} disabled={!selectedCustomer} className={`inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition ${selectedCustomer ? "border border-white/15 text-stone-100 hover:border-amber-300/45 hover:text-amber-200" : "cursor-not-allowed border border-white/10 text-stone-500"}`}>
                Save selected customer
              </button>
              <button type="button" onClick={resetCustomerDraft} className="inline-flex items-center gap-2 rounded-full border border-white/10 px-5 py-3 text-sm font-semibold text-stone-300 transition hover:border-white/20 hover:text-white">
                Reset form
              </button>
            </div>
          </article>
        </div>
      </section>

      <section className="container grid gap-8 px-6 py-14 lg:grid-cols-[0.95fr_1.05fr]">
        <article className="rounded-[2rem] border border-white/10 bg-stone-900/80 p-6">
          <p className="text-xs uppercase tracking-[0.25em] text-amber-300/75">Service coverage</p>
          <h2 className="mt-2 text-3xl font-semibold text-white">Service-backed modules surfaced inside the core experience</h2>
          <div className="mt-6 space-y-3">
            {(platformOverview?.serviceHealth ?? []).map((service) => (
              <div key={service.name} className="rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
                <div className="flex items-center justify-between gap-4">
                  <h3 className="text-base font-semibold text-stone-100">{service.name}</h3>
                  <span className={`rounded-full border px-3 py-1 text-xs ${statusTone(service.status)}`}>{service.status}</span>
                </div>
                <p className="mt-2 text-sm leading-7 text-stone-300">{service.description}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {service.dependencies.map((dependency) => (
                    <span key={dependency} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-stone-300">
                      {dependency}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {platformLoading ? <p className="text-sm text-stone-400">Refreshing integrated service posture…</p> : null}
          </div>
        </article>

        <article className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-6">
          <p className="text-xs uppercase tracking-[0.25em] text-stone-500">Recent activity</p>
          <h2 className="mt-2 text-3xl font-semibold text-white">Operational history visible across embedded modules</h2>
          <div className="mt-6 space-y-4">
            {activityFeed.map((activity) => (
              <div key={activity.id} className="flex gap-4 rounded-[1.4rem] border border-white/10 bg-stone-950/45 p-4">
                <div className="mt-1 rounded-full border border-amber-300/40 p-2 text-amber-300">
                  <CheckCircle2 size={14} />
                </div>
                <div>
                  <p className="text-sm font-medium text-stone-100">{activity.actor}</p>
                  <p className="mt-1 text-sm text-stone-300">{activity.action}</p>
                  <p className="mt-1 text-xs text-stone-500">{activity.entity} · {activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <footer className="border-t border-white/10 bg-stone-950/90">
        <div className="container flex flex-col gap-4 px-6 py-8 text-sm text-stone-400 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="text-base font-semibold text-stone-200">54link-dev core banking surface</h3>
            <p className="mt-1 max-w-2xl">Built around customer operations, integrated product workflows, teller and ledger control, ERP visibility, dispute handling, and agricultural finance monitoring.</p>
          </div>
          <a href="#top" className="inline-flex items-center gap-2 text-stone-300 transition hover:text-amber-200">
            Back to top <Waves size={16} />
          </a>
        </div>
      </footer>
    </main>
  );
}
