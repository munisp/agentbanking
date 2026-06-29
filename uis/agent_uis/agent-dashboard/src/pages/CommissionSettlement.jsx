import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpRight,
  Banknote,
  Calendar,
  CheckCircle,
  ChevronDown,
  Clock,
  Download,
  Info,
  Loader2,
  RefreshCw,
  TrendingUp,
  Wallet,
  XCircle,
} from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";
import { agentApi, authHeaders, commissionApi } from "../utils/api";

const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";
const PAYMENT_HUB_SWITCH_NAME = "mojaloop";
const PAYMENT_HUB_AMS_NAME = "core_banking";

// ─── helpers ─────────────────────────────────────────────────────────────────
const fmt = (n, cur = "NGN") =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: cur,
    maximumFractionDigits: 2,
  }).format(n || 0);

const dateStr = (d) =>
  d
    ? new Date(d).toLocaleDateString("en-NG", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "—";

const monthRange = () => {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
    .toISOString()
    .slice(0, 10);
  const end = now.toISOString().slice(0, 10);
  return { start, end };
};

const TX_META = {
  deposit: {
    label: "Deposit / Cash-In",
    icon: ArrowDownLeft,
    iconCls: "bg-green-50 text-green-600",
    amtCls: "text-green-700",
  },
  withdrawal: {
    label: "Withdrawal / Cash-Out",
    icon: ArrowUpRight,
    iconCls: "text-white",
    amtCls: "font-bold",
    bg: "rgba(0, 79, 113, 0.1)",
    color: "var(--tenant-primary-color,#004F71)",
  },
  transfer: {
    label: "Transfer",
    icon: ArrowUpRight,
    iconCls: "text-white",
    amtCls: "font-bold",
    bg: "rgba(0, 63, 90, 0.1)",
    color: "var(--tenant-primary-color,#003F5A)",
  },
  bill_payment: {
    label: "Bill Payment",
    icon: Banknote,
    iconCls: "bg-orange-50 text-orange-600",
    amtCls: "text-orange-700",
  },
  airtime: {
    label: "Airtime",
    icon: Banknote,
    iconCls: "bg-purple-50 text-purple-600",
    amtCls: "text-purple-700",
  },
  data: {
    label: "Data",
    icon: Banknote,
    iconCls: "bg-pink-50 text-pink-600",
    amtCls: "text-pink-700",
  },
};

const STATUS_BADGE = {
  pending: "bg-yellow-100 text-yellow-700",
  processing: "bg-gray-100 text-gray-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

// ─────────────────────────────────────────────────────────────────────────────
const CommissionSettlement = () => {
  // ── state ────────────────────────────────────────────────────────────────
  const [agentUUID, setAgentUUID] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [balance, setBalance] = useState(null);
  const [commissions, setCommissions] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [settlementsTotal, setSettlementsTotal] = useState(0);

  const [activeTab, setActiveTab] = useState("overview");
  const [showFeeInfo, setShowFeeInfo] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);

  // withdrawal_allowed comes from the balance API (policy-driven)
  const [withdrawalAllowed, setWithdrawalAllowed] = useState(true);
  const [minWithdrawalAmount, setMinWithdrawalAmount] = useState(0);

  // withdraw modal
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const emptyWF = () => ({
    destinationType: "agent_account",
    bankName: "",
    accountNumber: "",
    accountName: "",
  });
  const [withdrawForm, setWithdrawForm] = useState(emptyWF());
  const [agentBankAccount, setAgentBankAccount] = useState(null);
  const [agentAccounts, setAgentAccounts] = useState([]);
  const [selectedAgentAccountNumber, setSelectedAgentAccountNumber] =
    useState("");
  const [accountsLoading, setAccountsLoading] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [withdrawError, setWithdrawError] = useState(null);

  // ── data fetching ─────────────────────────────────────────────────────────
  const loadData = useCallback(async (uuid) => {
    const { start, end } = monthRange();
    const [balRes, comRes, setRes] = await Promise.allSettled([
      commissionApi.getBalance(uuid),
      commissionApi.listCommissions(uuid, {
        start_date: start,
        end_date: end,
        limit: 100,
      }),
      commissionApi.listSettlements(uuid, { limit: 20 }),
    ]);
    if (balRes.status === "fulfilled") {
      setBalance(balRes.value);
      setWithdrawalAllowed(balRes.value?.withdrawal_allowed !== false);
      setMinWithdrawalAmount(balRes.value?.min_withdrawal_amount ?? 0);
    }
    if (comRes.status === "fulfilled") {
      setCommissions(comRes.value.commissions ?? []);
    }
    if (setRes.status === "fulfilled") {
      setSettlements(setRes.value.settlements ?? []);
      setSettlementsTotal(setRes.value.total ?? 0);
    }
  }, []);

  const init = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const keycloakId = localStorage.getItem("keycloakId");
      if (!keycloakId) throw new Error("Not logged in");

      let uuid = keycloakId;

      const storedUserRaw = localStorage.getItem("user");
      if (storedUserRaw) {
        try {
          const storedUser = JSON.parse(storedUserRaw);
          uuid = storedUser?.id ?? null;
        } catch {
          uuid = null;
        }
      }

      if (!uuid) {
        const profileRes = await agentApi.getProfile(keycloakId);
        const profile = profileRes?.agent ?? profileRes;
        uuid = keycloakId;
      }

      setAccountsLoading(true);
      try {
        const response = await fetch(
          `${CORE_BANKING_URL}/account/account/keycloak/${keycloakId}`,
          {
            headers: authHeaders(),
          },
        );

        if (!response.ok) {
          throw new Error("Failed to fetch agent accounts");
        }

        const accountRes = await response.json();
        const accountsData = Array.isArray(accountRes)
          ? accountRes
          : accountRes?.account
            ? [accountRes.account]
            : accountRes?.accounts || accountRes?.data || [];

        setAgentAccounts(accountsData);

        const account = accountsData[0] ?? null;
        if (account) {
          setAgentBankAccount({
            bankName: account.bank_name ?? account.bank ?? "",
            accountNumber: account.account_number ?? "",
            accountName: account.account_name ?? account.name ?? "",
          });
          setSelectedAgentAccountNumber(account.account_number ?? "");
        }
      } catch {
        setAgentAccounts([]);
        setAgentBankAccount(null);
        setSelectedAgentAccountNumber("");
      } finally {
        setAccountsLoading(false);
      }

      if (!uuid) throw new Error("Could not resolve agent ID");
      setAgentUUID(uuid);
      await loadData(uuid);
    } catch (err) {
      setError(err?.message ?? "Failed to load commission data");
    } finally {
      setLoading(false);
    }
  }, [loadData]);

  useEffect(() => {
    init();
  }, [init]);

  // ── derived ───────────────────────────────────────────────────────────────
  const commissionsByType = commissions.reduce((acc, c) => {
    const type = c.transaction_type ?? "other";
    if (!acc[type]) acc[type] = { count: 0, total: 0 };
    acc[type].count += 1;
    acc[type].total += c.commission_amount ?? 0;
    return acc;
  }, {});
  const totalThisMonth = Object.values(commissionsByType).reduce(
    (s, v) => s + v.total,
    0,
  );
  const recentCommissions = [...commissions].sort(
    (a, b) =>
      new Date(b.earned_at ?? b.created_at) -
      new Date(a.earned_at ?? a.created_at),
  );
  const pendingBalance = balance?.pending_balance ?? 0;
  const availableBalance = balance?.available_balance ?? 0;
  const pendingFromList = commissions.reduce(
    (sum, commission) =>
      commission?.status === "pending"
        ? sum + (commission?.commission_amount ?? 0)
        : sum,
    0,
  );
  // Withdrawable = available_balance (already moved from pending by settlement creation)
  // Fall back to pending amounts so the UI isn't confusingly empty on first load
  const withdrawableAmount = availableBalance > 0
    ? availableBalance
    : Math.max(pendingBalance, pendingFromList);
  const earnedAmount = pendingBalance + availableBalance;
  const hasWithdrawableCommissions = withdrawableAmount > 0 && withdrawableAmount >= minWithdrawalAmount;
  const isAgentDestination = withdrawForm.destinationType === "agent_account";

  // ── withdraw ──────────────────────────────────────────────────────────────
  const canWithdraw =
    withdrawalAllowed &&
    hasWithdrawableCommissions &&
    withdrawableAmount >= minWithdrawalAmount &&
    withdrawForm.bankName &&
    withdrawForm.accountNumber &&
    withdrawForm.accountName;

  const openWithdrawModal = () => {
    setWithdrawError(null);
    setWithdrawForm((prev) => {
      const firstAccount = agentAccounts[0];
      const defaultAgentAccount = firstAccount
        ? {
            bankName: firstAccount.bank_name ?? firstAccount.bank ?? "",
            accountNumber: firstAccount.account_number ?? "",
            accountName: firstAccount.account_name ?? firstAccount.name ?? "",
          }
        : agentBankAccount;

      if (
        (prev.destinationType ?? "agent_account") === "agent_account" &&
        defaultAgentAccount
      ) {
        return {
          ...prev,
          destinationType: "agent_account",
          bankName: defaultAgentAccount.bankName || prev.bankName,
          accountNumber:
            defaultAgentAccount.accountNumber || prev.accountNumber,
          accountName: defaultAgentAccount.accountName || prev.accountName,
        };
      }
      return prev;
    });
    setShowWithdrawModal(true);
  };

  const handleWithdraw = async () => {
    if (!withdrawalAllowed) {
      setWithdrawError("Withdrawals are currently disabled by the platform administrator.");
      return;
    }
    if (withdrawableAmount < minWithdrawalAmount) {
      setWithdrawError(`Minimum withdrawal amount is ₦${minWithdrawalAmount.toLocaleString()}.`);
      return;
    }

    setWithdrawing(true);
    setWithdrawError(null);
    const { start, end } = monthRange();

    try {
      // Create settlement with auto_process=true so the commission-settlement
      // service handles the actual fund movement via settlement-payout.
      // No direct payment-hub call needed here — keeps payment and tracking in sync.
      const settlement = await commissionApi.requestSettlement({
        agent_id: agentUUID,
        payment_method: "bank_transfer",
        payment_details: {
          source_account_type: "mint_account",
          destination_type: withdrawForm.destinationType,
          bank_name: withdrawForm.bankName,
          account_number: withdrawForm.accountNumber,
          account_name: withdrawForm.accountName,
        },
        start_date: new Date(start).toISOString(),
        end_date: new Date(end + "T23:59:59").toISOString(),
        auto_process: true,
      });

      setShowWithdrawModal(false);
      setWithdrawForm(emptyWF());

      const statusMsg = settlement?.status === "completed"
        ? "Withdrawal processed — funds will arrive within 24 hours."
        : "Withdrawal request submitted — pending processing.";
      setSuccessMsg(statusMsg);
      await loadData(agentUUID);
      setTimeout(() => setSuccessMsg(null), 6000);
    } catch (err) {
      setWithdrawError(err?.message ?? "Withdrawal failed. Please try again.");
    } finally {
      setWithdrawing(false);
    }
  };

  // ── loading / error ───────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2
          className="w-7 h-7 animate-spin"
          style={{ color: "var(--tenant-primary-color,#004F71)" }}
        />
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-10 h-10 text-red-400" />
        <p className="text-gray-600">{error}</p>
        <button
          onClick={init}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)]"
        >
          <RefreshCw className="w-4 h-4" /> Retry
        </button>
      </div>
    );
  }

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Commission & Earnings
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Your commission wallet — withdraw to your bank any time
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadData(agentUUID)}
            title="Refresh"
            className="p-2 text-gray-400 hover:text-gray-600 rounded-xl border border-gray-200 hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={openWithdrawModal}
            disabled={!withdrawalAllowed || !hasWithdrawableCommissions}
            title={!withdrawalAllowed ? "Withdrawals paused by administrator" : !hasWithdrawableCommissions ? `Minimum withdrawal: ${fmt(minWithdrawalAmount)}` : ""}
            className="flex items-center gap-2 px-5 py-2.5 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Banknote className="w-4 h-4" />
            Withdraw
          </button>
        </div>
      </div>

      {/* Success banner */}
      {successMsg && (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
          <CheckCircle className="w-5 h-5 text-green-600 shrink-0" />
          <p className="text-sm text-green-700 font-medium">{successMsg}</p>
        </div>
      )}

      {/* Balance hero card */}
      <div
        className="rounded-2xl p-6 text-white relative overflow-hidden"
        style={{
          background:
            "linear-gradient(to bottom right, var(--tenant-primary-color,#004F71), #003F5A, var(--tenant-primary-color,#003047))",
        }}
      >
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 right-0 w-64 h-64 bg-white rounded-full -translate-y-32 translate-x-32" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-white rounded-full translate-y-24 -translate-x-24" />
        </div>
        <div className="relative">
          <div className="flex items-center gap-2 mb-1">
            <Wallet
              className="w-4 h-4"
              style={{ color: "rgba(255,255,255,0.7)" }}
            />
            <p
              className="text-sm font-medium"
              style={{ color: "rgba(255,255,255,0.7)" }}
            >
              Earned Amount
            </p>
          </div>
          <p className="text-4xl font-bold tracking-tight">
            {fmt(earnedAmount)}
          </p>
          <p
            className="text-xs mt-1"
            style={{ color: "rgba(255,255,255,0.7)" }}
          >
            {withdrawalAllowed
              ? `Available to withdraw · Last settled: ${balance?.last_settlement_at ? dateStr(balance.last_settlement_at) : "Never"}`
              : "Withdrawals are currently paused by the platform"}
          </p>
          <div className="mt-5 grid grid-cols-4 gap-3 border-t border-white/20 pt-4">
            <div>
              <p className="text-xs" style={{ color: "rgba(255,255,255,0.7)" }}>
                Pending
              </p>
              <p className="text-base font-bold mt-0.5">
                {fmt(balance?.pending_balance)}
              </p>
            </div>
            <div>
              <p className="text-xs" style={{ color: "rgba(255,255,255,0.7)" }}>
                Available
              </p>
              <p className="text-base font-bold mt-0.5 text-green-300">
                {fmt(availableBalance)}
              </p>
            </div>
            <div>
              <p className="text-xs" style={{ color: "rgba(255,255,255,0.7)" }}>
                This month
              </p>
              <p className="text-base font-bold mt-0.5">{fmt(totalThisMonth)}</p>
            </div>
            <div>
              <p className="text-xs" style={{ color: "rgba(255,255,255,0.7)" }}>
                Lifetime
              </p>
              <p className="text-base font-bold mt-0.5">
                {fmt(balance?.total_earned)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Fee info accordion */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <button
          onClick={() => setShowFeeInfo(!showFeeInfo)}
          className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors text-left"
        >
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4" style={{ color: "var(--tenant-primary-color,#004F71)" }} />
            <span className="text-sm font-semibold text-gray-800">
              How commissions are calculated
            </span>
          </div>
          <ChevronDown
            className={`w-4 h-4 text-gray-400 transition-transform ${showFeeInfo ? "rotate-180" : ""}`}
          />
        </button>
        {showFeeInfo && (
          <div className="px-5 pb-5 border-t border-gray-100">
            <p className="text-xs text-gray-500 pt-3 leading-relaxed">
              Commissions are calculated per transaction based on CBN
              inter-scheme fee sharing rules and your agent tier. Default rates
              — Cash-In: 0.1% · Cash-Out: 0.2% · Transfers: 0.15% · Bill
              Payments: 0.5% · Airtime / Data: 3%. Your network commissions
              accumulate as <em>pending</em> and become <em>available</em> after
              the settlement cycle.
            </p>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {[
          { key: "overview", label: "This Month" },
          { key: "history", label: "Withdrawals" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── This Month ─────────────────────────────────────────────────────── */}
      {activeTab === "overview" && (
        <div className="space-y-4 max-h-[40vh] overflow-scroll">
          {commissions.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 flex flex-col items-center gap-3 text-center">
              <TrendingUp className="w-10 h-10 text-gray-300" />
              <p className="font-semibold text-gray-600">
                No commissions this month yet
              </p>
              <p className="text-sm text-gray-400">
                Complete transactions to start earning commissions.
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Object.entries(commissionsByType).map(([type, data]) => {
                  const meta = TX_META[type] ?? {
                    label: type.replace(/_/g, " "),
                    icon: Banknote,
                    iconCls: "bg-gray-50 text-gray-500",
                    amtCls: "text-gray-700",
                  };
                  const Icon = meta.icon;
                  return (
                    <div
                      key={type}
                      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex items-center gap-4"
                    >
                      <div
                        className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${meta.iconCls}`}
                      >
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-gray-800">
                          {meta.label}
                        </p>
                        <p className="text-xs text-gray-400">
                          {data.count.toLocaleString()} transaction
                          {data.count !== 1 ? "s" : ""}
                        </p>
                      </div>
                      <p className={`text-base font-bold ${meta.amtCls}`}>
                        {fmt(data.total)}
                      </p>
                    </div>
                  );
                })}
              </div>

              {/* Month total */}
              <div className="bg-linear-to-r from-green-500 to-emerald-600 rounded-2xl p-5 text-white flex items-center justify-between">
                <div>
                  <p className="text-green-100 text-sm font-medium">
                    Total Earned — This Month
                  </p>
                  <p className="text-3xl font-bold mt-1">
                    {fmt(totalThisMonth)}
                  </p>
                  <p className="text-green-200 text-xs mt-1">
                    {commissions.length} commission record
                    {commissions.length !== 1 ? "s" : ""}
                  </p>
                </div>
                <button
                  onClick={openWithdrawModal}
                  disabled={!withdrawalAllowed || !hasWithdrawableCommissions}
                  className="flex items-center gap-2 px-4 py-2 bg-white text-green-700 rounded-xl text-sm font-semibold hover:bg-green-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Banknote className="w-4 h-4" />
                  Withdraw Now
                </button>
              </div>

              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                  <h2 className="text-sm font-bold text-gray-800">
                    Commission Details
                  </h2>
                  <span className="text-xs text-gray-400">
                    {recentCommissions.length} item
                    {recentCommissions.length !== 1 ? "s" : ""}
                  </span>
                </div>

                <div className="divide-y divide-gray-50">
                  {recentCommissions.map((commission) => {
                    const meta = TX_META[commission.transaction_type] ?? {
                      label: (commission.transaction_type ?? "other").replace(
                        /_/g,
                        " ",
                      ),
                      icon: Banknote,
                      iconCls: "bg-gray-50 text-gray-500",
                      amtCls: "text-gray-700",
                    };
                    const Icon = meta.icon;

                    return (
                      <div
                        key={commission.id}
                        className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors"
                      >
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${meta.iconCls}`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>

                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-gray-800 capitalize">
                            {meta.label}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5 truncate">
                            Ref: {commission.transaction_ref}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {dateStr(
                              commission.earned_at ?? commission.created_at,
                            )}
                          </p>
                        </div>

                        <div className="text-right">
                          <p className="text-sm font-bold text-gray-900">
                            {fmt(
                              commission.commission_amount,
                              commission.currency ?? "NGN",
                            )}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5">
                            Rate:{" "}
                            {(Number(commission.rate ?? 0) * 100).toFixed(2)}%
                          </p>
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium mt-1 ${STATUS_BADGE[commission.status] ?? "bg-blue-100 text-blue-700"}`}
                          >
                            {commission.status ?? "unknown"}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Withdrawals ───────────────────────────────────────────────────── */}
      {activeTab === "history" && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-800">
              Withdrawal History
              {settlementsTotal > 0 && (
                <span className="ml-2 text-gray-400 font-normal">
                  ({settlementsTotal})
                </span>
              )}
            </h2>
            <button
              className="flex items-center gap-1.5 text-xs font-medium"
              style={{ color: "var(--tenant-primary-color,#004F71)" }}
            >
              <Download className="w-3.5 h-3.5" /> Export
            </button>
          </div>
          {settlements.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-14 text-center">
              <Clock className="w-10 h-10 text-gray-300" />
              <p className="text-sm font-semibold text-gray-600">
                No withdrawals yet
              </p>
              <p className="text-xs text-gray-400">
                Your completed withdrawal history will appear here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {settlements.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors"
                >
                  <div
                    className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                      s.status === "completed"
                        ? "bg-green-100"
                        : s.status === "failed"
                          ? "bg-red-100"
                          : "bg-yellow-100"
                    }`}
                  >
                    {s.status === "completed" ? (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    ) : s.status === "failed" ? (
                      <XCircle className="w-5 h-5 text-red-500" />
                    ) : (
                      <Clock className="w-5 h-5 text-yellow-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-800 capitalize">
                      {s.payment_method?.replace(/_/g, " ")} ·{" "}
                      {s.commission_count} commission
                      {s.commission_count !== 1 ? "s" : ""}
                    </p>
                    <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
                      <Calendar className="w-3 h-3" />
                      {dateStr(s.created_at)} · {s.settlement_ref}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-gray-900">
                      {fmt(s.total_amount, s.currency ?? "NGN")}
                    </p>
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium mt-0.5 ${STATUS_BADGE[s.status] ?? STATUS_BADGE.pending}`}
                    >
                      {s.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Withdraw modal ────────────────────────────────────────────────── */}
      {showWithdrawModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-gray-900">
                Withdraw Commission
              </h2>
              <button
                onClick={() => setShowWithdrawModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            {/* Balance pill */}
            <div
              className="rounded-xl px-4 py-3 flex items-center justify-between"
              style={{ backgroundColor: "rgba(0,79,113,0.05)" }}
            >
              <div className="flex items-center gap-2">
                <Wallet className="w-4 h-4" style={{ color: "var(--tenant-primary-color,#004F71)" }} />
                <span
                  className="text-sm font-medium"
                  style={{ color: "var(--tenant-primary-color,#003047)" }}
                >
                  Earned Amount
                </span>
              </div>
              <span className="text-lg font-bold" style={{ color: "var(--tenant-primary-color,#004F71)" }}>
                {fmt(earnedAmount)}
              </span>
            </div>

            {!withdrawalAllowed && (
              <p className="text-sm text-red-700 bg-red-50 rounded-xl px-4 py-3">
                Withdrawals are currently paused by the platform administrator.
              </p>
            )}
            {withdrawalAllowed && !hasWithdrawableCommissions && (
              <p className="text-sm text-amber-700 bg-amber-50 rounded-xl px-4 py-3">
                {minWithdrawalAmount > 0
                  ? `Minimum withdrawal is ${fmt(minWithdrawalAmount)}. Keep earning!`
                  : "No commissions available to withdraw yet."}
              </p>
            )}

            {/* Transfer source */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Transfer source
              </label>
              <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                Mint Account → Beneficiary Bank Account (Bank Transfer)
              </div>
            </div>

            {/* Destination account */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Destination account
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: "agent_account", label: "Agent Account" },
                  { value: "other_account", label: "Other Account" },
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => {
                      if (option.value === "agent_account") {
                        const firstAccount = agentAccounts[0];
                        setWithdrawForm((prev) => ({
                          ...prev,
                          destinationType: option.value,
                          bankName:
                            firstAccount?.bank_name ??
                            firstAccount?.bank ??
                            agentBankAccount?.bankName ??
                            prev.bankName,
                          accountNumber:
                            firstAccount?.account_number ??
                            agentBankAccount?.accountNumber ??
                            prev.accountNumber,
                          accountName:
                            firstAccount?.account_name ??
                            firstAccount?.name ??
                            agentBankAccount?.accountName ??
                            prev.accountName,
                        }));
                        if (firstAccount?.account_number) {
                          setSelectedAgentAccountNumber(
                            firstAccount.account_number,
                          );
                        }
                        return;
                      }

                      setWithdrawForm((prev) => ({
                        ...prev,
                        destinationType: option.value,
                      }));
                    }}
                    className={`py-2 px-2 rounded-xl border text-xs font-medium transition-colors ${
                      withdrawForm.destinationType === option.value
                        ? "bg-[var(--tenant-secondary-color,#69BC5E)] bg-opacity-20 border-[var(--tenant-secondary-color,#69BC5E)] text-[var(--tenant-primary-color,#004F71)]"
                        : "border-gray-200 text-gray-600 hover:border-gray-300"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>

              <div className="mt-3">
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Agent account list
                </label>
                <select
                  value={selectedAgentAccountNumber}
                  onChange={(e) => {
                    const selected = agentAccounts.find(
                      (account) => account.account_number === e.target.value,
                    );

                    setSelectedAgentAccountNumber(e.target.value);
                    if (!selected) return;

                    setWithdrawForm((prev) => ({
                      ...prev,
                      destinationType: "agent_account",
                      bankName: selected.bank_name ?? selected.bank ?? "",
                      accountNumber: selected.account_number ?? "",
                      accountName: selected.account_name ?? selected.name ?? "",
                    }));
                  }}
                  disabled={accountsLoading || agentAccounts.length === 0}
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                >
                  <option value="">
                    {accountsLoading
                      ? "Loading accounts..."
                      : agentAccounts.length > 0
                        ? "Select an agent account"
                        : "No agent accounts found"}
                  </option>
                  {agentAccounts.map((account) => (
                    <option
                      key={account.account_number || account.id}
                      value={account.account_number || ""}
                    >
                      {(account.account_name ||
                        account.name ||
                        "Agent Account") +
                        " • " +
                        (account.account_number || "—")}
                    </option>
                  ))}
                </select>
              </div>

              {isAgentDestination && !agentBankAccount?.accountNumber && (
                <p className="mt-2 text-xs text-amber-700 bg-amber-50 rounded-xl px-3 py-2">
                  Agent account details were not found automatically. Fill
                  beneficiary details manually.
                </p>
              )}
            </div>

            {/* Beneficiary bank fields */}
            <div className="space-y-3">
              {[
                {
                  key: "bankName",
                  label: "Beneficiary bank name",
                  placeholder: "e.g. Access Bank",
                },
                {
                  key: "accountNumber",
                  label: "Beneficiary account number",
                  placeholder: "10-digit NUBAN",
                },
                {
                  key: "accountName",
                  label: "Beneficiary account name",
                  placeholder: "Name on account",
                },
              ].map((f) => (
                <div key={f.key}>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    {f.label}
                  </label>
                  <input
                    type="text"
                    placeholder={f.placeholder}
                    value={withdrawForm[f.key]}
                    onChange={(e) =>
                      setWithdrawForm({
                        ...withdrawForm,
                        [f.key]: e.target.value,
                      })
                    }
                    readOnly={
                      isAgentDestination &&
                      !!agentBankAccount?.accountNumber &&
                      (f.key === "accountNumber" || f.key === "accountName")
                    }
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 read-only:bg-gray-50 read-only:text-gray-500"
                  />
                </div>
              ))}
            </div>

            <p className="text-xs text-gray-500 bg-gray-50 rounded-xl px-4 py-3">
              Commission funds will be transferred from the platform to the
              selected beneficiary account. Funds typically arrive within 24 hours.
            </p>

            {withdrawError && (
              <p className="text-red-600 text-sm bg-red-50 rounded-xl px-4 py-3">
                {withdrawError}
              </p>
            )}

            <div className="flex gap-3 pt-1">
              <button
                onClick={() => setShowWithdrawModal(false)}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleWithdraw}
                disabled={!canWithdraw || withdrawing}
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {withdrawing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Processing…
                  </>
                ) : (
                  "Request Withdrawal"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CommissionSettlement;
