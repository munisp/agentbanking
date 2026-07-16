import {
    AlertCircle,
    CheckCircle2,
    ExternalLink,
    Loader2,
    ShieldAlert,
    UserCheck,
} from "lucide-react";
import { useState } from "react";

/**
 * Blocking KYC verification modal — mirrors the tenant_admin KYCVerificationDialog.
 * Cannot be dismissed: user must either complete KYC or log out.
 */
export function KYCVerificationModal({ open, kycUrl, onComplete, onLogout }) {
  const [isRedirecting, setIsRedirecting] = useState(false);

  if (!open) return null;

  const handleCompleteKyc = () => {
    if (kycUrl) {
      setIsRedirecting(true);
      window.open(kycUrl, "_blank", "noopener,noreferrer");
      // Close modal and mark as acknowledged after brief delay
      setTimeout(() => {
        setIsRedirecting(false);
        if (onComplete) onComplete();
      }, 1000);
    }
  };

  return (
    /* Backdrop — pointer-events-auto so clicks don't pass through */
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 px-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-8 space-y-6">
        {/* Icon */}
        <div className="flex flex-col items-center text-center space-y-4 pt-2">
          <div className="relative">
            <div className="absolute inset-0 bg-amber-400/20 rounded-full blur-xl animate-pulse" />
            <div className="relative flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-amber-500 to-orange-500 shadow-lg">
              <ShieldAlert className="h-10 w-10 text-white" />
            </div>
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-gray-900">
              KYC Verification Required
            </h2>
            <p className="text-gray-500 text-sm leading-relaxed max-w-sm mx-auto">
              To ensure the security of our platform and comply with regulatory
              requirements, you need to complete your identity verification
              before accessing your account.
            </p>
          </div>
        </div>

        {/* Info cards */}
        <div className="space-y-3">
          <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-50 border border-blue-200">
            <UserCheck className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-blue-900">
                Why KYC is Required
              </p>
              <p className="text-sm text-blue-700 mt-1">
                KYC (Know Your Customer) verification helps us protect your
                account and maintain a secure banking environment for all users.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-4 rounded-xl bg-green-50 border border-green-200">
            <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-green-900">
                Quick &amp; Simple Process
              </p>
              <p className="text-sm text-green-700 mt-1">
                The verification process only takes a few minutes. You'll need a
                valid government-issued ID and a clear photo.
              </p>
            </div>
          </div>

          {!kycUrl && (
            <div className="flex items-start gap-3 p-4 rounded-xl bg-red-50 border border-red-200">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-red-900">
                  Verification Link Unavailable
                </p>
                <p className="text-sm text-red-700 mt-1">
                  Your KYC verification link is not available. Please contact
                  support for assistance or try logging in again.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          {kycUrl ? (
            <>
              <button
                onClick={onLogout}
                className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 transition-colors text-sm"
              >
                Logout
              </button>
              <button
                onClick={handleCompleteKyc}
                disabled={isRedirecting}
                className="flex-1 py-3 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-xl font-semibold transition-colors text-sm flex items-center justify-center gap-2 shadow-md disabled:opacity-70"
              >
                {isRedirecting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Opening…
                  </>
                ) : (
                  <>
                    Complete Verification
                    <ExternalLink className="w-4 h-4" />
                  </>
                )}
              </button>
            </>
          ) : (
            <button
              onClick={onLogout}
              className="w-full py-3 bg-gray-800 text-white rounded-xl font-semibold hover:bg-gray-900 transition-colors text-sm"
            >
              Logout &amp; Contact Support
            </button>
          )}
        </div>

        {kycUrl && (
          <p className="text-xs text-center text-gray-400">
            After completing verification, please log in again to access your
            account.
          </p>
        )}
      </div>
    </div>
  );
}

export default KYCVerificationModal;
