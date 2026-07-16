import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const ProtectedRoute = () => {
  const { isAuthenticated, isLoading, user, logout } = useAuth();

  const normalizedKycStatus = String(
    user?.kycStatus ?? user?.kyc_verification_status ?? "",
  )
    .trim()
    .toLowerCase();
  const isKycPending = isAuthenticated && normalizedKycStatus === "pending";

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <>
      <Outlet />

      {isKycPending && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-gray-900/70 px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h2 className="text-xl font-bold text-gray-900">KYC Pending</h2>
            <p className="mt-2 text-sm text-gray-600">
              Your account is signed in, but verification is still pending. Complete KYC to continue full access.
            </p>

            <div className="mt-6 flex gap-3">
              {user?.kycUrl ? (
                <a
                  href={user.kycUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="flex-1 rounded-xl bg-green-600 px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-green-700"
                >
                  Continue KYC
                </a>
              ) : (
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="flex-1 rounded-xl bg-green-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-700"
                >
                  Refresh Status
                </button>
              )}

              <button
                type="button"
                onClick={logout}
                className="flex-1 rounded-xl border border-gray-300 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ProtectedRoute;
