import {
    Activity,
    ArrowUpRight,
    BarChart3,
    CheckCircle,
    ChevronRight,
    CreditCard,
    FileText,
    Globe,
    Heart,
    Landmark,
    LayoutGrid,
    PiggyBank,
    QrCode,
    Radio,
    ShieldCheck,
    Smartphone,
    ToggleLeft,
    ToggleRight,
    TrendingUp,
    Users,
    Wallet,
    Zap,
} from "lucide-react";
import React, { useState } from "react";

// ----- service catalogue ----- //
const serviceGroups = [
  {
    group: "Payments & Collections",
    services: [
      {
        id: "bill_payment",
        name: "Bill Payment",
        desc: "Electricity (EKEDC, IBEDC, AEDC), DSTV, GOtv, Startimes, internet data",
        icon: Zap,
        color: {
          bg: "bg-yellow-50",
          text: "text-yellow-600",
          ring: "ring-yellow-200",
        },
        commissionLabel: "₦50–₦150 flat / bill",
        monthlyEarnings: 12450,
        monthlyTxns: 183,
        enabled: true,
        setupRequired: false,
      },
      {
        id: "airtime_data",
        name: "Airtime & Data Sales",
        desc: "Airtime top-up and data bundles for MTN, Airtel, Glo, 9mobile",
        icon: Smartphone,
        color: {
          bg: "bg-green-50",
          text: "text-green-600",
          ring: "ring-green-200",
        },
        commissionLabel: "2–3% of face value",
        monthlyEarnings: 8320,
        monthlyTxns: 412,
        enabled: true,
        setupRequired: false,
      },
      {
        id: "qr_payments",
        name: "QR Payments",
        desc: "Accept payments from walk-in customers via 54agent QR or NQR",
        icon: QrCode,
        color: {
          bg: "bg-blue-50",
          text: "text-blue-600",
          ring: "ring-blue-200",
        },
        commissionLabel: "0.5% of transaction",
        monthlyEarnings: 6790,
        monthlyTxns: 238,
        enabled: true,
        setupRequired: false,
      },
      {
        id: "govt_collections",
        name: "Government Collections",
        desc: "LGA levies, state taxes, VAT, NIMC enrolment ID fees, court fines",
        icon: Landmark,
        color: {
          bg: "bg-indigo-50",
          text: "text-indigo-600",
          ring: "ring-indigo-200",
        },
        commissionLabel: "₦75–₦200 flat / payment",
        monthlyEarnings: 4150,
        monthlyTxns: 47,
        enabled: true,
        setupRequired: true,
      },
    ],
  },
  {
    group: "Financial Products",
    services: [
      {
        id: "insurance",
        name: "Micro-Insurance",
        desc: "Sell hospital cash, crop, gadget & life cover policies starting at ₦500/month",
        icon: ShieldCheck,
        color: {
          bg: "bg-teal-50",
          text: "text-teal-600",
          ring: "ring-teal-200",
        },
        commissionLabel: "10–15% of premium",
        monthlyEarnings: 3200,
        monthlyTxns: 29,
        enabled: true,
        setupRequired: true,
      },
      {
        id: "savings_collection",
        name: "Savings Collection (Ajo/Esusu)",
        desc: "Daily/weekly savings collection for market women & SMEs — digital susu wallet",
        icon: PiggyBank,
        color: {
          bg: "bg-pink-50",
          text: "text-pink-600",
          ring: "ring-pink-200",
        },
        commissionLabel: "₦25 per collection",
        monthlyEarnings: 5875,
        monthlyTxns: 235,
        enabled: true,
        setupRequired: false,
      },
      {
        id: "loan_origination",
        name: "Loan Origination",
        desc: "Refer customers for instant nano-loans (₦5k–₦200k). Earn referral fee per approved loan",
        icon: Wallet,
        color: {
          bg: "bg-purple-50",
          text: "text-purple-600",
          ring: "ring-purple-200",
        },
        commissionLabel: "2% of disbursed amount",
        monthlyEarnings: 11600,
        monthlyTxns: 18,
        enabled: false,
        setupRequired: true,
      },
    ],
  },
];

const allServices = serviceGroups.flatMap((g) => g.services);

const totalMonthlyEarnings = allServices.reduce(
  (s, x) => s + (x.enabled ? x.monthlyEarnings : 0),
  0,
);
const totalMonthlyTxns = allServices.reduce(
  (s, x) => s + (x.enabled ? x.monthlyTxns : 0),
  0,
);

// bar widths for relative chart
const maxEarnings = Math.max(...allServices.map((s) => s.monthlyEarnings));

const Services = () => {
  const [services, setServices] = useState(
    allServices.reduce((acc, s) => ({ ...acc, [s.id]: s.enabled }), {}),
  );
  const [activeGroup, setActiveGroup] = useState("all");
  const [setupModal, setSetupModal] = useState(null);
  const [justEnabled, setJustEnabled] = useState(null);

  const toggle = (id, needsSetup) => {
    if (!services[id] && needsSetup) {
      setSetupModal(allServices.find((s) => s.id === id));
      return;
    }
    setServices((prev) => ({ ...prev, [id]: !prev[id] }));
    if (!services[id]) {
      setJustEnabled(id);
      setTimeout(() => setJustEnabled(null), 3000);
    }
  };

  const enableFromModal = () => {
    if (!setupModal) return;
    setServices((prev) => ({ ...prev, [setupModal.id]: true }));
    setJustEnabled(setupModal.id);
    setTimeout(() => setJustEnabled(null), 3000);
    setSetupModal(null);
  };

  const enabledCount = Object.values(services).filter(Boolean).length;
  const currentEarnings = allServices.reduce(
    (s, x) => s + (services[x.id] ? x.monthlyEarnings : 0),
    0,
  );

  const displayedGroups =
    activeGroup === "all"
      ? serviceGroups
      : serviceGroups.filter(
          (g) => g.group.toLowerCase().replace(/\s/g, "_") === activeGroup,
        );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Services & Revenue Streams
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Enable additional services to diversify your income beyond Cash-In /
            Cash-Out
          </p>
        </div>
        <div className="flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-xl px-4 py-2">
          <LayoutGrid className="w-4 h-4 text-blue-600" />
          <span className="text-sm font-semibold text-blue-700">
            {enabledCount} of {allServices.length} active
          </span>
        </div>
      </div>

      {/* Success banner */}
      {justEnabled && (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
          <CheckCircle className="w-5 h-5 text-green-600 shrink-0" />
          <p className="text-sm text-green-800 font-medium">
            <strong>
              {allServices.find((s) => s.id === justEnabled)?.name}
            </strong>{" "}
            is now active — you can start earning immediately.
          </p>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-linear-to-br from-blue-600 to-indigo-700 rounded-2xl p-5 text-white">
          <p className="text-blue-200 text-xs font-medium flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5" /> Service Earnings — Feb 2026
          </p>
          <p className="text-3xl font-bold mt-1">
            ₦{currentEarnings.toLocaleString()}
          </p>
          <p className="text-blue-200 text-xs mt-1">
            from {enabledCount} active services
          </p>
        </div>
        <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
          <p className="text-gray-400 text-xs font-medium flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5" /> Total Service Transactions
          </p>
          <p className="text-3xl font-bold mt-1 text-gray-900">
            {allServices
              .reduce((s, x) => s + (services[x.id] ? x.monthlyTxns : 0), 0)
              .toLocaleString()}
          </p>
          <p className="text-gray-400 text-xs mt-1">this month, all services</p>
        </div>
        <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
          <p className="text-gray-400 text-xs font-medium flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" /> Avg per Service
          </p>
          <p className="text-3xl font-bold mt-1 text-gray-900">
            ₦
            {enabledCount
              ? Math.round(currentEarnings / enabledCount).toLocaleString()
              : 0}
          </p>
          <p className="text-gray-400 text-xs mt-1">revenue / active service</p>
        </div>
      </div>

      {/* Earnings bar chart */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
        <h2 className="text-sm font-bold text-gray-800 mb-4">
          Revenue Breakdown by Service
        </h2>
        <div className="space-y-3">
          {[...allServices]
            .sort((a, b) => b.monthlyEarnings - a.monthlyEarnings)
            .map((svc) => {
              const widthPct = Math.round(
                (svc.monthlyEarnings / maxEarnings) * 100,
              );
              const isOn = services[svc.id];
              return (
                <div key={svc.id} className="flex items-center gap-3">
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${svc.color.bg} ${svc.color.text}`}
                  >
                    <svc.icon className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1 gap-2">
                      <span
                        className={`text-xs font-medium truncate ${isOn ? "text-gray-700" : "text-gray-400"}`}
                      >
                        {svc.name}
                      </span>
                      <span
                        className={`text-xs font-bold shrink-0 ${isOn ? "text-gray-900" : "text-gray-400"}`}
                      >
                        ₦{svc.monthlyEarnings.toLocaleString()}
                      </span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${isOn ? svc.color.bg.replace("50", "400") : "bg-gray-200"}`}
                        style={{
                          width: `${widthPct}%`,
                          filter: isOn ? "none" : "grayscale(1)",
                        }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Group Filter */}
      <div className="flex gap-2 flex-wrap">
        {[
          { key: "all", label: "All Services" },
          { key: "payments_&_collections", label: "Payments" },
          { key: "financial_products", label: "Financial Products" },
        ].map((f) => (
          <button
            key={f.key}
            onClick={() => setActiveGroup(f.key)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              activeGroup === f.key
                ? "bg-blue-600 text-white"
                : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Service groups */}
      {displayedGroups.map((grp) => (
        <div key={grp.group} className="space-y-3">
          <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
            {grp.group}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {grp.services.map((svc) => {
              const isOn = services[svc.id];
              return (
                <div
                  key={svc.id}
                  className={`bg-white rounded-2xl border shadow-sm overflow-hidden transition-all ${
                    isOn ? "border-gray-100" : "border-gray-100 opacity-70"
                  }`}
                >
                  <div className="p-5">
                    <div className="flex items-start gap-4">
                      <div
                        className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 ${svc.color.bg} ${svc.color.text}`}
                      >
                        <svc.icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h3 className="text-sm font-bold text-gray-900">
                              {svc.name}
                            </h3>
                            {svc.setupRequired && !isOn && (
                              <span className="inline-block mt-0.5 text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-md font-medium">
                                Setup required
                              </span>
                            )}
                          </div>
                          {/* Toggle */}
                          <button
                            onClick={() => toggle(svc.id, svc.setupRequired)}
                            className="shrink-0 mt-0.5"
                            title={isOn ? "Disable service" : "Enable service"}
                          >
                            {isOn ? (
                              <ToggleRight
                                className={`w-8 h-8 ${svc.color.text}`}
                              />
                            ) : (
                              <ToggleLeft className="w-8 h-8 text-gray-300" />
                            )}
                          </button>
                        </div>
                        <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                          {svc.desc}
                        </p>
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                      <div
                        className={`rounded-xl py-2 ${isOn ? svc.color.bg : "bg-gray-50"}`}
                      >
                        <p className="text-xs text-gray-500">Earnings</p>
                        <p
                          className={`text-sm font-bold mt-0.5 ${isOn ? svc.color.text : "text-gray-400"}`}
                        >
                          ₦{svc.monthlyEarnings.toLocaleString()}
                        </p>
                      </div>
                      <div
                        className={`rounded-xl py-2 ${isOn ? "bg-gray-50" : "bg-gray-50"}`}
                      >
                        <p className="text-xs text-gray-500">Txns</p>
                        <p
                          className={`text-sm font-bold mt-0.5 ${isOn ? "text-gray-800" : "text-gray-400"}`}
                        >
                          {svc.monthlyTxns}
                        </p>
                      </div>
                      <div className={`rounded-xl py-2 bg-gray-50`}>
                        <p className="text-xs text-gray-500">Commission</p>
                        <p className="text-xs font-semibold mt-0.5 text-gray-600 leading-tight">
                          {svc.commissionLabel}
                        </p>
                      </div>
                    </div>

                    {isOn && (
                      <div className="mt-3 flex items-center gap-1 text-xs text-green-600 font-medium">
                        <CheckCircle className="w-3.5 h-3.5" />
                        Active · earning this month
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Setup modal */}
      {setupModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-gray-900">
                Enable {setupModal.name}
              </h2>
              <button
                onClick={() => setSetupModal(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <div
              className={`flex items-center gap-3 p-4 rounded-xl ${setupModal.color.bg}`}
            >
              <setupModal.icon className={`w-8 h-8 ${setupModal.color.text}`} />
              <div>
                <p className={`text-sm font-bold ${setupModal.color.text}`}>
                  {setupModal.name}
                </p>
                <p className="text-xs text-gray-600 mt-0.5">
                  {setupModal.commissionLabel}
                </p>
              </div>
            </div>
            <div className="space-y-3">
              <div className="text-sm text-gray-700 leading-relaxed">
                {setupModal.desc}
              </div>
              <div className="bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 text-xs text-amber-800 space-y-1">
                <p className="font-semibold">Before activation:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  <li>Confirm your KYC level 2 is complete</li>
                  <li>Review the service terms and commission schedule</li>
                  <li>
                    Activation is instant — a 54agent ops agent may follow up
                    for onboarding
                  </li>
                </ul>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setSetupModal(null)}
                className="flex-1 py-2.5 border border-gray-300 rounded-xl text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={enableFromModal}
                className={`flex-1 py-2.5 rounded-xl text-sm font-semibold text-white transition-colors ${setupModal.color.bg.replace("bg-", "bg-").replace("-50", "-600")} hover:opacity-90`}
              >
                I agree — Enable Service
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Services;
