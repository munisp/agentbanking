import { useCallback, useEffect, useState } from "react";
import Joyride, { STATUS, EVENTS, ACTIONS } from "react-joyride";
import type { CallBackProps, Step, TooltipRenderProps } from "react-joyride";

const TOUR_KEY = "54link_admin_tour_v1";

const STEPS: Step[] = [
  {
    target: "body",
    content: (
      <div>
        <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 8 }}>Welcome to the Super Admin Console</h2>
        <p style={{ fontSize: 13, color: "#6B7280", lineHeight: 1.5 }}>
          This quick tour walks you through every section of the sidebar. You can restart it anytime using the Guide Tour button at the bottom.
        </p>
      </div>
    ),
    placement: "center",
    disableBeacon: true,
  },
  {
    target: "[data-tour='section-overview']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Overview</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Your command centre — platform-wide metrics, tenant activity, transaction volumes, and system health at a glance.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='section-administration']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Administration</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Manage admin accounts, tenants, businesses, transactions, BNPL, and feature flags across the entire platform.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='section-billing']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Billing</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>View and manage billing accounts for all tenants — subscription plans, invoices, and payment status.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='section-audit-compliance']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Audit & Compliance</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Full audit trail of all admin actions, temporal access grants, and your own permission review — essential for regulatory oversight.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='section-monitoring-alerts']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Monitoring & Alerts</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Real-time system health, API latency, error rates, and configurable threshold alerts for transactions and infrastructure events.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='section-developer']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Developer</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Manage API keys, review developer app submissions, monitor API usage, and control third-party integrations.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='tour-help']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Restart This Tour</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Click here anytime to replay this guide. You're all set — happy administrating!</p>
      </div>
    ),
    placement: "top",
    disableBeacon: true,
  },
];

function CustomTooltip({ continuous, index, step, backProps, primaryProps, skipProps, tooltipProps, size }: TooltipRenderProps) {
  return (
    <div
      {...tooltipProps}
      style={{
        maxWidth: 340,
        borderRadius: 14,
        padding: 0,
        overflow: "hidden",
        boxShadow: "0 20px 40px rgba(0,0,0,0.18)",
        background: "white",
      }}
    >
      <div style={{ background: "linear-gradient(135deg, #004F71 0%, #003047 100%)", padding: "12px 16px 10px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ color: "#6CC049", fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" }}>
            Admin Guide
          </span>
          <button
            {...skipProps}
            style={{ background: "none", border: "none", color: "rgba(255,255,255,0.55)", cursor: "pointer", fontSize: 11, padding: "2px 6px" }}
          >
            Skip
          </button>
        </div>
      </div>

      <div style={{ padding: "16px 20px" }}>{step.content}</div>

      <div style={{ background: "#F9FAFB", padding: "10px 16px", display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: "1px solid #E5E7EB" }}>
        <span style={{ fontSize: 12, color: "#9CA3AF" }}>{index + 1} / {size}</span>
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
            style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: "linear-gradient(135deg, #004F71, #003047)", color: "white", fontSize: 13, cursor: "pointer", fontWeight: 600 }}
          >
            {continuous ? (index === size - 1 ? "Finish" : "Next") : "Got it"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppTour({ run, onFinish }: { run: boolean; onFinish: () => void }) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (run) setStepIndex(0);
  }, [run]);

  const handleCallback = useCallback(
    (data: CallBackProps) => {
      const { status, type, action, index } = data;

      if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
        localStorage.setItem(TOUR_KEY, "true");
        setStepIndex(0);
        onFinish();
        return;
      }

      // Advance past steps whose section is hidden by permissions
      if (type === EVENTS.TARGET_NOT_FOUND) {
        setStepIndex(index + (action === ACTIONS.PREV ? -1 : 1));
        return;
      }

      if (type === EVENTS.STEP_AFTER) {
        setStepIndex(index + (action === ACTIONS.PREV ? -1 : 1));
      }
    },
    [onFinish],
  );

  return (
    <Joyride
      steps={STEPS}
      run={run}
      stepIndex={stepIndex}
      continuous
      scrollToFirstStep
      showSkipButton
      disableOverlayClose
      spotlightClicks={false}
      tooltipComponent={CustomTooltip}
      styles={{
        options: {
          zIndex: 10000,
          overlayColor: "rgba(0, 79, 113, 0.45)",
          arrowColor: "white",
        },
        spotlight: { borderRadius: 8 },
      }}
      callback={handleCallback}
    />
  );
}

export function useTour() {
  const [run, setRun] = useState(false);

  useEffect(() => {
    const done = localStorage.getItem(TOUR_KEY);
    if (!done) {
      const t = setTimeout(() => setRun(true), 900);
      return () => clearTimeout(t);
    }
  }, []);

  const startTour = useCallback(() => setRun(true), []);
  const stopTour = useCallback(() => setRun(false), []);

  return { run, startTour, stopTour };
}
