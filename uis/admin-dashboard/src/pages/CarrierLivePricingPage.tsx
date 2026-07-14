import DashboardLayout from "@/components/DashboardLayout";
import { useState } from "react";

import { trpc } from "@/lib/trpc";
export default function CarrierLivePricingPage() {
  const [countryFilter, setCountryFilter] = useState("all");
  const [estimateCarrier, setEstimateCarrier] = useState("mtn_ng");
  const [smsCount, setSmsCount] = useState(1000);
  const [ussdSessions, setUssdSessions] = useState(500);
  const [dataMb, setDataMb] = useState(100);

  const carriers = [
    {
      id: "mtn_ng",
      name: "MTN Nigeria",
      country: "NG",
      currency: "NGN",
      sms: 4.0,
      ussd: 1.63,
      data: 3.5,
      voice: 11.26,
      source: "AT API",
    },
    {
      id: "airtel_ng",
      name: "Airtel Nigeria",
      country: "NG",
      currency: "NGN",
      sms: 4.0,
      ussd: 1.63,
      data: 3.0,
      voice: 11.0,
      source: "AT API",
    },
    {
      id: "glo_ng",
      name: "Glo Nigeria",
      country: "NG",
      currency: "NGN",
      sms: 4.0,
      ussd: 1.63,
      data: 2.5,
      voice: 11.0,
      source: "Direct",
    },
    {
      id: "9mobile_ng",
      name: "9Mobile Nigeria",
      country: "NG",
      currency: "NGN",
      sms: 4.0,
      ussd: 1.63,
      data: 3.2,
      voice: 12.0,
      source: "Direct",
    },
    {
      id: "safaricom_ke",
      name: "Safaricom Kenya",
      country: "KE",
      currency: "KES",
      sms: 1.0,
      ussd: 0.5,
      data: 2.0,
      voice: 4.0,
      source: "AT API",
    },
    {
      id: "mtn_gh",
      name: "MTN Ghana",
      country: "GH",
      currency: "GHS",
      sms: 0.05,
      ussd: 0.03,
      data: 0.08,
      voice: 0.15,
      source: "AT API",
    },
    {
      id: "vodafone_gh",
      name: "Vodafone Ghana",
      country: "GH",
      currency: "GHS",
      sms: 0.05,
      ussd: 0.03,
      data: 0.07,
      voice: 0.14,
      source: "Direct",
    },
    {
      id: "orange_sn",
      name: "Orange Senegal",
      country: "SN",
      currency: "XOF",
      sms: 25.0,
      ussd: 15.0,
      data: 20.0,
      voice: 50.0,
      source: "Direct",
    },
    {
      id: "mtn_za",
      name: "MTN South Africa",
      country: "ZA",
      currency: "ZAR",
      sms: 0.5,
      ussd: 0.2,
      data: 0.85,
      voice: 1.5,
      source: "AT API",
    },
    {
      id: "vodacom_za",
      name: "Vodacom South Africa",
      country: "ZA",
      currency: "ZAR",
      sms: 0.55,
      ussd: 0.22,
      data: 0.9,
      voice: 1.6,
      source: "Direct",
    },
    {
      id: "ethio_et",
      name: "Ethio Telecom",
      country: "ET",
      currency: "ETB",
      sms: 0.4,
      ussd: 0.2,
      data: 0.6,
      voice: 0.8,
      source: "Direct",
    },
    {
      id: "airtel_tz",
      name: "Airtel Tanzania",
      country: "TZ",
      currency: "TZS",
      sms: 25.0,
      ussd: 15.0,
      data: 30.0,
      voice: 60.0,
      source: "AT API",
    },
  ];

  const countries = [...new Set(carriers.map(c => c.country))];
  const filtered =
    countryFilter === "all"
      ? carriers
      : carriers.filter(c => c.country === countryFilter);
  const selectedCarrier = carriers.find(c => c.id === estimateCarrier);
  const smsCost = selectedCarrier ? smsCount * selectedCarrier.sms : 0;
  const ussdCost = selectedCarrier ? ussdSessions * selectedCarrier.ussd : 0;
  const dataCost = selectedCarrier ? dataMb * selectedCarrier.data : 0;
  const totalCost = smsCost + ussdCost + dataCost;
  // Sprint 87: Wired to carrierSwitching router
  const { data, isLoading } = trpc.carrierSwitching.list.useQuery({
    // @ts-ignore Sprint 85
    page: 1,
    limit: 10,
  });

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white">
            Carrier Live Pricing
          </h1>
          <div className="flex gap-2">
            <button
              onClick={() => setCountryFilter("all")}
              className={`px-3 py-1 rounded text-sm ${countryFilter === "all" ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-300"}`}
            >
              All
            </button>
            {countries.map(c => (
              <button
                key={c}
                onClick={() => setCountryFilter(c)}
                className={`px-3 py-1 rounded text-sm ${countryFilter === c ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-300"}`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-gray-800 rounded overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-700">
              <tr>
                <th className="text-left p-3 text-gray-300 text-sm">Carrier</th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Country
                </th>
                <th className="text-right p-3 text-gray-300 text-sm">
                  SMS Rate
                </th>
                <th className="text-right p-3 text-gray-300 text-sm">
                  USSD Rate
                </th>
                <th className="text-right p-3 text-gray-300 text-sm">
                  Data/MB
                </th>
                <th className="text-right p-3 text-gray-300 text-sm">
                  Voice/Min
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Source
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => (
                <tr
                  key={c.id}
                  className="border-t border-gray-700 hover:bg-gray-750"
                >
                  <td className="p-3 text-white">{c.name}</td>
                  <td className="p-3 text-center text-gray-300">{c.country}</td>
                  <td className="p-3 text-right text-white">
                    {c.currency} {c.sms.toFixed(2)}
                  </td>
                  <td className="p-3 text-right text-white">
                    {c.currency} {c.ussd.toFixed(2)}
                  </td>
                  <td className="p-3 text-right text-white">
                    {c.currency} {c.data.toFixed(2)}
                  </td>
                  <td className="p-3 text-right text-white">
                    {c.currency} {c.voice.toFixed(2)}
                  </td>
                  <td className="p-3 text-center">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${c.source === "AT API" ? "bg-green-900 text-green-300" : "bg-blue-900 text-blue-300"}`}
                    >
                      {c.source}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-gray-800 rounded p-6">
          <h2 className="text-lg font-semibold text-white mb-4">
            Cost Estimator
          </h2>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <label className="text-gray-400 text-sm">Carrier</label>
              <select
                value={estimateCarrier}
                onChange={e => setEstimateCarrier(e.target.value)}
                className="w-full mt-1 bg-gray-700 text-white rounded p-2"
              >
                {carriers.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-gray-400 text-sm">SMS Count</label>
              <input
                type="number"
                value={smsCount}
                onChange={e => setSmsCount(Number(e.target.value))}
                className="w-full mt-1 bg-gray-700 text-white rounded p-2"
              />
            </div>
            <div>
              <label className="text-gray-400 text-sm">USSD Sessions</label>
              <input
                type="number"
                value={ussdSessions}
                onChange={e => setUssdSessions(Number(e.target.value))}
                className="w-full mt-1 bg-gray-700 text-white rounded p-2"
              />
            </div>
            <div>
              <label className="text-gray-400 text-sm">Data (MB)</label>
              <input
                type="number"
                value={dataMb}
                onChange={e => setDataMb(Number(e.target.value))}
                className="w-full mt-1 bg-gray-700 text-white rounded p-2"
              />
            </div>
          </div>
          {selectedCarrier && (
            <div className="mt-4 grid grid-cols-4 gap-4">
              <div className="bg-gray-700 rounded p-3">
                <div className="text-gray-400 text-xs">SMS Cost</div>
                <div className="text-white font-bold">
                  {selectedCarrier.currency}{" "}
                  {smsCost.toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}
                </div>
              </div>
              <div className="bg-gray-700 rounded p-3">
                <div className="text-gray-400 text-xs">USSD Cost</div>
                <div className="text-white font-bold">
                  {selectedCarrier.currency}{" "}
                  {ussdCost.toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}
                </div>
              </div>
              <div className="bg-gray-700 rounded p-3">
                <div className="text-gray-400 text-xs">Data Cost</div>
                <div className="text-white font-bold">
                  {selectedCarrier.currency}{" "}
                  {dataCost.toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}
                </div>
              </div>
              <div className="bg-blue-900 rounded p-3">
                <div className="text-blue-300 text-xs">Total Estimated</div>
                <div className="text-white font-bold text-lg">
                  {selectedCarrier.currency}{" "}
                  {totalCost.toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
