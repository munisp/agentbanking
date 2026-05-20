// CarrierCostDashboard — Sprint 77
// Interactive carrier cost comparison across all carriers with SMS/data/USSD/voice pricing
import { useState, useMemo } from "react";
import { trpc } from "@/lib/trpc";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { DollarSign, TrendingDown, BarChart3, Globe } from "lucide-react";

export default function CarrierCostDashboard() {
  const [country, setCountry] = useState("NG");
  const [smsCount, setSmsCount] = useState(1000);
  const [dataMb, setDataMb] = useState(500);
  const [ussdSessions, setUssdSessions] = useState(200);
  const [voiceMinutes, setVoiceMinutes] = useState(100);

  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const rates = trpc.carrierCost.listRates.useQuery({ country });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const comparison = trpc.carrierCost.compareForUsage.useQuery({
    country,
    smsCount,
    dataMb,
    ussdSessions,
    voiceMinutes,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const countries = trpc.carrierCost.listCountries.useQuery();

  return (
    <DashboardLayout>
      <div className="container py-6 space-y-6">
        <div className="flex items-center gap-3">
          <DollarSign className="h-8 w-8 text-green-500" />
          <div>
            <h1 className="text-2xl font-bold">Carrier Cost Optimization</h1>
            <p className="text-muted-foreground">
              Compare SMS, data, USSD, and voice costs across all carriers
            </p>
          </div>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5" /> Usage Parameters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <Select value={country} onValueChange={setCountry}>
                <SelectTrigger>
                  <SelectValue placeholder="Country" />
                </SelectTrigger>
                <SelectContent>
                  {(countries.data || []).map((c: any) => (
                    <SelectItem key={c.code} value={c.code}>
                      {c.name} ({c.code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div>
                <label className="text-xs text-muted-foreground">
                  SMS/month
                </label>
                <Input
                  type="number"
                  value={smsCount}
                  onChange={e => setSmsCount(+e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">
                  Data (MB)
                </label>
                <Input
                  type="number"
                  value={dataMb}
                  onChange={e => setDataMb(+e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">
                  USSD sessions
                </label>
                <Input
                  type="number"
                  value={ussdSessions}
                  onChange={e => setUssdSessions(+e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">
                  Voice (min)
                </label>
                <Input
                  type="number"
                  value={voiceMinutes}
                  onChange={e => setVoiceMinutes(+e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Cost Comparison Rankings */}
        {comparison.data && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingDown className="h-5 w-5" /> Cost Rankings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {comparison.data.map((c: any, i: number) => (
                  <div
                    key={c.carrier}
                    className="flex items-center justify-between p-4 rounded-lg bg-muted/50"
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className="text-2xl font-bold"
                        style={{
                          color:
                            i === 0
                              ? "#22c55e"
                              : i === 1
                                ? "#3b82f6"
                                : "#6b7280",
                        }}
                      >
                        #{c.rank}
                      </div>
                      <div>
                        <p className="font-semibold text-lg">{c.carrier}</p>
                        <p className="text-sm text-muted-foreground">
                          SMS: ${c.breakdown.sms.toFixed(2)} | Data: $
                          {c.breakdown.data.toFixed(2)} | USSD: $
                          {c.breakdown.ussd.toFixed(2)} | Voice: $
                          {c.breakdown.voice.toFixed(2)}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xl font-bold">
                        ${c.totalCostUsd.toFixed(2)}
                      </p>
                      {c.savingsVsWorst > 0 && (
                        <Badge variant="default" className="bg-green-600">
                          Save ${c.savingsVsWorst.toFixed(2)}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Rate Card Table */}
        {rates.data && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" /> Rate Card — {country}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Carrier</th>
                      <th className="text-right p-2">SMS ($/msg)</th>
                      <th className="text-right p-2">Data ($/MB)</th>
                      <th className="text-right p-2">USSD ($/session)</th>
                      <th className="text-right p-2">Voice ($/min)</th>
                      <th className="text-right p-2">Currency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rates.data.map((r: any) => (
                      <tr
                        key={r.carrier}
                        className="border-b hover:bg-muted/30"
                      >
                        <td className="p-2 font-medium">{r.carrier}</td>
                        <td className="p-2 text-right">
                          ${r.smsPerMessage.toFixed(4)}
                        </td>
                        <td className="p-2 text-right">
                          ${r.dataPerMb.toFixed(4)}
                        </td>
                        <td className="p-2 text-right">
                          ${r.ussdPerSession.toFixed(4)}
                        </td>
                        <td className="p-2 text-right">
                          ${r.voicePerMinute.toFixed(4)}
                        </td>
                        <td className="p-2 text-right">{r.currency}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
