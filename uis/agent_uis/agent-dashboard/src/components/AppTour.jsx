import React, { useCallback, useState } from "react";
import { Joyride, STATUS } from "react-joyride";

const TOUR_KEY = "agent_tour_completed_v1";

const STEPS = [
  {
    target: "body",
    content: (
      <div>
        <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 8 }}>Welcome to Your Agent Dashboard</h2>
        <p style={{ fontSize: 13, color: "#6B7280", lineHeight: 1.5 }}>
          This quick tour covers the key features available to you as an agent. You can restart it anytime from the sidebar.
        </p>
      </div>
    ),
    placement: "center",
    disableBeacon: true,
  },
  {
    target: "[data-tour='nav-dashboard']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Dashboard</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Your home screen — live balance, recent transactions, quick action buttons, and performance snapshot.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-transactions']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Transactions</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Full history of all your transactions with filters by date, type, and status. Download receipts from here.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-cash-in']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Cash In</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Accept cash deposits on behalf of customers. Enter the amount, confirm customer details, and issue a receipt.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-cash-out']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Cash Out</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Process cash withdrawals for customers. Verify identity and available balance before dispensing funds.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-transfer']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Transfer</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Send money to other accounts domestically. Supports interbank and intra-bank transfers with instant confirmation.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-bills']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Bill Payment & VAT</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Pay electricity, water, cable TV, and other utility bills for customers. VAT is automatically calculated and included.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-float']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Float Management</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Request float top-ups when your cash balance is low. Track your float usage and repayment history.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-commission']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Commission</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>View your earned commissions by transaction type, settlement status, and period. Track pending and paid amounts.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-training']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Training Academy</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Complete your CBN-mandatory courses (AML, KYC, Fraud Prevention). Earn certificates and stay compliant.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-achievements']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Achievements & Rewards</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Earn points for every transaction. Climb the leaderboard from Bronze to Diamond tier and unlock rewards.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-performance']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>My Performance</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Track your personal metrics — transaction volume, success rate, commission earned, and customer rating.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-loyalty']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Loyalty Points</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>View and manage your loyalty points account. Earn points on eligible transactions and redeem for rewards.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-pos']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>POS Terminals</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Manage your assigned POS devices, request new terminals, and view terminal health and transaction logs.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='nav-profile']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Your Profile</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Update your personal details, view your KYC status, change your PIN, and manage notification preferences.</p>
      </div>
    ),
    placement: "right",
  },
  {
    target: "[data-tour='tour-help']",
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 4 }}>Restart This Tour</h3>
        <p style={{ fontSize: 13, color: "#6B7280" }}>Click here anytime to replay this guide. You're all set — happy banking!</p>
      </div>
    ),
    placement: "right",
    disableBeacon: true,
  },
];

function CustomTooltip({ continuous, index, step, backProps, closeProps, primaryProps, skipProps, tooltipProps, size }) {
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
      {/* Header */}
      <div style={{ background: "linear-gradient(135deg, var(--tenant-primary-color,#004F71) 0%, #003047 100%)", padding: "12px 16px 10px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ color: "var(--tenant-secondary-color,#6CC049)", fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" }}>
            Agent Guide
          </span>
          <button
            {...skipProps}
            style={{ background: "none", border: "none", color: "rgba(255,255,255,0.55)", cursor: "pointer", fontSize: 11, padding: "2px 6px" }}
          >
            Skip
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: "16px 20px" }}>{step.content}</div>

      {/* Footer */}
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
            style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: "linear-gradient(135deg, var(--tenant-primary-color,#004F71), #003047)", color: "white", fontSize: 13, cursor: "pointer", fontWeight: 600 }}
          >
            {continuous ? (index === size - 1 ? "Finish" : "Next") : "Got it"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppTour({ run, onFinish }) {
  const handleCallback = useCallback(
    (data) => {
      if ([STATUS.FINISHED, STATUS.SKIPPED].includes(data.status)) {
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
  const [run, setRun] = useState(() => !localStorage.getItem(TOUR_KEY));

  const startTour = useCallback(() => setRun(true), []);
  const stopTour = useCallback(() => setRun(false), []);

  return { run, startTour, stopTour };
}
