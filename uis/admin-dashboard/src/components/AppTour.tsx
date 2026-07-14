import React, { useCallback, useEffect, useState } from "react";
import { Joyride, STATUS, Step, TooltipRenderProps, EventData } from "react-joyride";

const TOUR_KEY = "admin_tour_completed_v2";

const STEPS: Step[] = [
  {
    target: "body",
    content: (
      <div>
        <h2 className="text-lg font-bold mb-2">Welcome to the Admin Dashboard</h2>
        <p className="text-sm text-gray-600">
          This tour covers the key sections of the platform. You can skip it anytime or restart it from the help button in the sidebar.
        </p>
      </div>
    ),
    placement: "center",
    skipBeacon: true,
  },
  {
    target: "[data-tour='sidebar-nav']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Navigation Sidebar</h3>
        <p className="text-sm">All platform sections are grouped here by function — Overview, People, Finance, Compliance, and more.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-dashboard']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Dashboard</h3>
        <p className="text-sm">Your central overview — live transaction volumes, agent counts, system health, and KPIs at a glance.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-agents']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Agent Management</h3>
        <p className="text-sm">Onboard, approve, suspend, and monitor agents. View KYC status, float balance, commission history, and hierarchy.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-customers']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Customer Management</h3>
        <p className="text-sm">View all customers served through your agents. Track account status, KYC verification, and transaction history per customer.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-pos']",
    content: (
      <div>
        <h3 className="font-bold mb-1">POS & Field Devices</h3>
        <p className="text-sm">Manage POS terminal inventory, device provisioning, remote commands, tamper alerts, and geofence violation monitoring.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-transactions']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Transactions</h3>
        <p className="text-sm">Full transaction ledger with filtering by type, date, agent, and status. Every cash-in, cash-out, transfer, and bill payment is here.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-commission']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Commission & Settlements</h3>
        <p className="text-sm">Configure commission rules, view agent earnings, process settlement batches, and manage payout workflows.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-float-loans']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Float Loans</h3>
        <p className="text-sm">Review and manage agent float loan applications. Credit decisions are server-side — this view shows status, approvals, and outstanding float positions.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-reconciliation']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Settlement Reconciliation</h3>
        <p className="text-sm">Automated daily reconciliation between float balances, ledger entries, and settlement totals. Discrepancies are flagged here before they compound.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-billing']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Billing Engine</h3>
        <p className="text-sm">Platform revenue dashboard — credits, invoices, billing ledger, and payment history for institution billing and platform fees.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-gamification']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Agent Gamification</h3>
        <p className="text-sm">Leaderboard, achievement badges, and tier rankings (Bronze → Diamond) powered by the loyalty points engine.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-training']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Training Academy</h3>
        <p className="text-sm">Manage CBN-mandatory training courses (AML, KYC, Fraud, Data Privacy). Publish courses and track agent completion and certification status.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-performance']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Performance Leaderboard</h3>
        <p className="text-sm">Rank agents by volume, transaction count, commissions, or ratings across weekly, monthly, quarterly, or annual periods.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-disputes']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Disputes & Risk</h3>
        <p className="text-sm">Manage chargebacks, arbitration, customer portal disputes, and automated resolution rules. AI-assisted mediation available.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-compliance']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Compliance & Regulatory</h3>
        <p className="text-sm">Live KYC/AML dashboard, CBN report generation, NFIU reporting, GDPR data retention, and regulatory sandbox. All compliance obligations in one place.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-reports']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Reports & Analytics</h3>
        <p className="text-sm">Agent business reports, revenue forecasting, projections, and system-wide analytics. Export to CSV for regulatory submissions.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-developer']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Developer & API</h3>
        <p className="text-sm">Manage API keys, webhooks, review developer app submissions, monitor API usage and rate limits, and control third-party integrations.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-settings']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Settings</h3>
        <p className="text-sm">Configure tenant branding, notification preferences, system parameters, and admin role permissions.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='tour-help']",
    content: (
      <div>
        <h3 className="font-bold mb-1">Restart This Tour</h3>
        <p className="text-sm">Click here anytime to replay this guide. You're all set — welcome aboard!</p>
      </div>
    ),
    placement: "top",
    skipBeacon: true,
  },
];

function CustomTooltip({
  continuous,
  index,
  step,
  backProps,
  primaryProps,
  skipProps,
  tooltipProps,
  size,
}: TooltipRenderProps) {
  return (
    <div
      {...tooltipProps}
      style={{ maxWidth: 360, borderRadius: 12, padding: 0, overflow: "hidden", boxShadow: "0 20px 40px rgba(0,0,0,0.18)" }}
    >
      <div style={{ background: "linear-gradient(135deg, var(--tenant-primary-color,#002082) 0%, color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black) 100%)", padding: "12px 16px 10px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ color: "var(--tenant-secondary-color,#6CC049)", fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" }}>
            Platform Guide
          </span>
          <button
            {...skipProps}
            style={{ background: "none", border: "none", color: "rgba(255,255,255,0.6)", cursor: "pointer", fontSize: 11, padding: "2px 6px", borderRadius: 4 }}
          >
            Skip tour
          </button>
        </div>
      </div>

      <div style={{ background: "white", padding: "16px 20px" }}>
        {step.content}
      </div>

      <div style={{ background: "#F9FAFB", padding: "10px 16px", display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: "1px solid #E5E7EB" }}>
        <span style={{ fontSize: 12, color: "#6B7280" }}>
          {index + 1} / {size}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          {index > 0 && (
            <button
              {...backProps}
              style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid #D1D5DB", background: "white", color: "#374151", fontSize: 13, cursor: "pointer", fontWeight: 500 }}
            >
              Back
            </button>
          )}
          <button
            {...primaryProps}
            style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: "linear-gradient(135deg, var(--tenant-primary-color,#002082), color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black))", color: "white", fontSize: 13, cursor: "pointer", fontWeight: 600 }}
          >
            {continuous ? (index === size - 1 ? "Finish" : "Next") : "Got it"}
          </button>
        </div>
      </div>
    </div>
  );
}

interface AppTourProps {
  run: boolean;
  onFinish: () => void;
}

export function AppTour({ run, onFinish }: AppTourProps) {
  const handleEvent = useCallback(
    (data: EventData) => {
      if (data.status === STATUS.FINISHED || data.status === STATUS.SKIPPED) {
        localStorage.setItem(TOUR_KEY, "true");
        onFinish();
      }
    },
    [onFinish],
  );

  return (
    <Joyride
      steps={STEPS}
      run={run}
      continuous
      scrollToFirstStep
      tooltipComponent={CustomTooltip}
      onEvent={handleEvent}
      options={{
        overlayColor: "rgba(0, 32, 130, 0.45)",
        zIndex: 10000,
        overlayClickAction: false,
        targetWaitTimeout: 2000,
        showProgress: false,
      }}
    />
  );
}

export function useTour() {
  const [run, setRun] = useState(false);

  useEffect(() => {
    const done = localStorage.getItem(TOUR_KEY);
    if (!done) {
      const t = setTimeout(() => setRun(true), 800);
      return () => clearTimeout(t);
    }
  }, []);

  const startTour = useCallback(() => setRun(true), []);
  const stopTour = useCallback(() => setRun(false), []);

  return { run, startTour, stopTour };
}
