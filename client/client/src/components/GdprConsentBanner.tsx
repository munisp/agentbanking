/**
 * GdprConsentBanner.tsx — NDPR/GDPR Consent Banner
 *
 * Phase 104 (P3): GDPR/NDPR consent banner that gates the app until the user accepts
 * the data processing terms. Links to the existing gdpr.exportMyData and gdpr.requestErasure
 * procedures for data portability and right to erasure.
 *
 * Compliance:
 *  - NDPR Article 2.1(1)(a): Consent must be freely given, specific, informed, and unambiguous
 *  - GDPR Article 7: Conditions for consent
 *  - Stores consent timestamp in localStorage (keyed by agentId)
 *  - Shows "Manage My Data" link to the GDPR portal in the banner
 */

import { useState, useEffect } from "react";
import { X, Shield, Download, Trash2 } from "lucide-react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";

const DISP = "'Inter Variable', sans-serif";
const MONO = "'JetBrains Mono Variable', monospace";
const BLUE = "oklch(0.70 0.22 260)";
const RED = "oklch(0.65 0.22 25)";
const CARD = "oklch(0.18 0.015 230)";
const BORDER = "oklch(0.28 0.015 230)";

interface GdprConsentBannerProps {
  agentId?: string;
  /** If true, show the banner even if consent was previously given (for testing) */
  forceShow?: boolean;
}

export function GdprConsentBanner({
  agentId,
  forceShow = false,
}: GdprConsentBannerProps) {
  const [show, setShow] = useState(false);
  const [showDataPortal, setShowDataPortal] = useState(false);

  const exportMutation = trpc.gdpr.exportMyData.useQuery(undefined, {
    enabled: false, // manual trigger only
  });

  const erasureMutation = trpc.gdpr.requestErasure.useMutation({
    onSuccess: () => {
      toast.success(
        "Erasure request submitted. You will be notified when complete."
      );
      setShowDataPortal(false);
    },
    onError: (e: any) => {
      toast.error(`Erasure request failed: ${e.message}`);
    },
  });
  const isErasurePending = erasureMutation.isPending;

  useEffect(() => {
    if (!agentId) return;
    const key = `gdpr_consent_${agentId}`;
    const consent = localStorage.getItem(key);
    if (!consent || forceShow) {
      setShow(true);
    }
  }, [agentId, forceShow]);

  const handleAccept = () => {
    if (!agentId) return;
    const key = `gdpr_consent_${agentId}`;
    localStorage.setItem(
      key,
      JSON.stringify({ acceptedAt: new Date().toISOString() })
    );
    setShow(false);
    toast.success("Consent recorded. Thank you!");
  };

  const handleExportData = async () => {
    try {
      const result = await exportMutation.refetch();
      if (!result.data) throw new Error("No data returned");
      // Download as JSON file
      const blob = new Blob([JSON.stringify(result.data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `gdpr-export-${agentId}-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Data export downloaded successfully");
    } catch (e: any) {
      toast.error(`Export failed: ${e.message}`);
    }
  };

  const handleRequestErasure = () => {
    if (
      !confirm(
        "⚠️ This will permanently anonymise your personal data. Continue?"
      )
    )
      return;
    erasureMutation.mutate({
      reason: "User-requested via consent banner",
      confirmPhrase: "DELETE MY DATA",
    });
  };

  if (!show) return null;

  return (
    <>
      {/* Main consent banner */}
      <div
        className="fixed bottom-0 left-0 right-0 z-50 p-4 md:p-6"
        style={{
          background:
            "linear-gradient(to top, oklch(0.10 0.015 230), transparent)",
        }}
      >
        <div
          className="max-w-4xl mx-auto rounded-2xl p-6 shadow-2xl"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div className="flex items-start gap-4">
            <div
              className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center"
              style={{ background: "oklch(0.60 0.22 260 / 0.2)" }}
            >
              <Shield className="w-6 h-6" style={{ color: BLUE }} />
            </div>
            <div className="flex-1">
              <h3
                className="text-lg font-bold text-white mb-2"
                style={{ fontFamily: DISP }}
              >
                Your Privacy Matters — NDPR/GDPR Compliance
              </h3>
              <p
                className="text-sm text-gray-400 mb-4"
                style={{ fontFamily: DISP }}
              >
                We process your personal data (name, phone, BVN, transaction
                history) to provide financial services in compliance with the{" "}
                <strong>Nigeria Data Protection Regulation (NDPR)</strong> and{" "}
                <strong>GDPR</strong>. By continuing, you consent to this
                processing. You can export or request erasure of your data at
                any time.
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleAccept}
                  className="px-6 py-2.5 rounded-lg font-semibold text-sm transition-all hover:scale-105"
                  style={{ background: BLUE, color: "white", fontFamily: DISP }}
                >
                  Accept & Continue
                </button>
                <button
                  onClick={() => setShowDataPortal(true)}
                  className="px-6 py-2.5 rounded-lg font-semibold text-sm transition-all"
                  style={{
                    background: "oklch(0.25 0.015 230)",
                    color: "white",
                    fontFamily: DISP,
                  }}
                >
                  Manage My Data
                </button>
                <a
                  href="/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-2.5 rounded-lg font-semibold text-sm transition-all"
                  style={{
                    background: "transparent",
                    color: BLUE,
                    border: `1px solid ${BLUE}`,
                    fontFamily: DISP,
                  }}
                >
                  Privacy Policy
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Data management portal modal */}
      {showDataPortal && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ background: "oklch(0.10 0.015 230 / 0.95)" }}
        >
          <div
            className="max-w-2xl w-full rounded-2xl p-8 shadow-2xl"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div className="flex items-center justify-between mb-6">
              <h2
                className="text-2xl font-bold text-white"
                style={{ fontFamily: DISP }}
              >
                Manage My Data
              </h2>
              <button
                onClick={() => setShowDataPortal(false)}
                className="w-10 h-10 rounded-full flex items-center justify-center transition-all hover:scale-110"
                style={{ background: "oklch(0.25 0.015 230)" }}
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="flex flex-col gap-4">
              {/* Export data */}
              <div
                className="rounded-xl p-6"
                style={{
                  background: "oklch(0.15 0.015 230)",
                  border: `1px solid ${BORDER}`,
                }}
              >
                <div className="flex items-start gap-4">
                  <div
                    className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center"
                    style={{ background: "oklch(0.60 0.22 260 / 0.2)" }}
                  >
                    <Download className="w-6 h-6" style={{ color: BLUE }} />
                  </div>
                  <div className="flex-1">
                    <h3
                      className="text-lg font-bold text-white mb-2"
                      style={{ fontFamily: DISP }}
                    >
                      Export My Data
                    </h3>
                    <p
                      className="text-sm text-gray-400 mb-4"
                      style={{ fontFamily: DISP }}
                    >
                      Download a JSON file containing all your personal data:
                      profile, transactions, audit log, loyalty history, and KYC
                      sessions.
                    </p>
                    <button
                      onClick={handleExportData}
                      disabled={
                        exportMutation.isLoading || exportMutation.isFetching
                      }
                      className="px-6 py-2.5 rounded-lg font-semibold text-sm transition-all hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{
                        background: BLUE,
                        color: "white",
                        fontFamily: DISP,
                      }}
                    >
                      {exportMutation.isLoading || exportMutation.isFetching
                        ? "Exporting..."
                        : "Download My Data"}
                    </button>
                  </div>
                </div>
              </div>

              {/* Request erasure */}
              <div
                className="rounded-xl p-6"
                style={{
                  background: "oklch(0.15 0.015 230)",
                  border: `1px solid ${BORDER}`,
                }}
              >
                <div className="flex items-start gap-4">
                  <div
                    className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center"
                    style={{ background: "oklch(0.60 0.22 25 / 0.2)" }}
                  >
                    <Trash2 className="w-6 h-6" style={{ color: RED }} />
                  </div>
                  <div className="flex-1">
                    <h3
                      className="text-lg font-bold text-white mb-2"
                      style={{ fontFamily: DISP }}
                    >
                      Request Data Erasure
                    </h3>
                    <p
                      className="text-sm text-gray-400 mb-4"
                      style={{ fontFamily: DISP }}
                    >
                      Request permanent anonymisation of your personal data.
                      Your transaction history will be preserved for audit
                      compliance (CBN requirement), but all PII (name, phone,
                      email, BVN, NIN) will be erased.
                    </p>
                    <button
                      onClick={handleRequestErasure}
                      disabled={isErasurePending}
                      className="px-6 py-2.5 rounded-lg font-semibold text-sm transition-all hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{
                        background: RED,
                        color: "white",
                        fontFamily: DISP,
                      }}
                    >
                      {isErasurePending ? "Submitting..." : "Request Erasure"}
                    </button>
                  </div>
                </div>
              </div>

              <p
                className="text-xs text-gray-500 mt-4"
                style={{ fontFamily: MONO }}
              >
                All requests are logged in the audit trail. Erasure requests are
                processed within 30 days as required by NDPR Article 2.1(1)(d).
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
