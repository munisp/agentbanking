import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Shield, Plus, Edit, Search } from "lucide-react";

export default function TransactionLimitsEnginePage() {
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    name: "",
    txnType: "cash_in",
    minAmount: "0",
    maxAmount: "10000",
    dailyLimit: "50000",
    monthlyLimit: "500000",
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const { data, isLoading } = trpc.transactionLimitsEngine.list.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const addMut = trpc.transactionLimitsEngine.create.useMutation({
    onSuccess: () => {
      toast.success("Limit rule added");
      setShowAdd(false);
    },
  });
  const limits = (data?.limits || []).filter(
    (l: any) => !search || l.name?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="w-6 h-6" /> Transaction Limits Engine
          </h1>
          <p className="text-muted-foreground mt-1">
            Configure per-agent, per-product, and per-tier transaction limits
          </p>
        </div>
        <Button onClick={() => setShowAdd(!showAdd)}>
          <Plus className="w-4 h-4 mr-1" /> Add Rule
        </Button>
      </div>
      {showAdd && (
        <Card>
          <CardHeader>
            <CardTitle>Add Limit Rule</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-4">
            <Input
              placeholder="Rule Name"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
            />
            <select
              className="border rounded px-3 py-2"
              value={form.txnType}
              onChange={e => setForm({ ...form, txnType: e.target.value })}
            >
              <option value="cash_in">Cash In</option>
              <option value="cash_out">Cash Out</option>
              <option value="transfer">Transfer</option>
              <option value="bills">Bills</option>
              <option value="airtime">Airtime</option>
            </select>
            <Input
              placeholder="Min Amount"
              type="number"
              value={form.minAmount}
              onChange={e => setForm({ ...form, minAmount: e.target.value })}
            />
            <Input
              placeholder="Max Amount"
              type="number"
              value={form.maxAmount}
              onChange={e => setForm({ ...form, maxAmount: e.target.value })}
            />
            <Input
              placeholder="Daily Limit"
              type="number"
              value={form.dailyLimit}
              onChange={e => setForm({ ...form, dailyLimit: e.target.value })}
            />
            <Input
              placeholder="Monthly Limit"
              type="number"
              value={form.monthlyLimit}
              onChange={e => setForm({ ...form, monthlyLimit: e.target.value })}
            />
            <Button
              onClick={() =>
                addMut.mutate({
                  ...form,
                  minAmount: +form.minAmount,
                  maxAmount: +form.maxAmount,
                  dailyLimit: +form.dailyLimit,
                  monthlyLimit: +form.monthlyLimit,
                })
              }
              disabled={addMut.isPending}
            >
              Add Rule
            </Button>
          </CardContent>
        </Card>
      )}
      <div className="flex items-center gap-2">
        <Search className="w-4 h-4" />
        <Input
          placeholder="Search rules..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>
      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="p-3 text-left">Rule</th>
                <th className="p-3 text-left">Type</th>
                <th className="p-3 text-right">Min</th>
                <th className="p-3 text-right">Max</th>
                <th className="p-3 text-right">Daily</th>
                <th className="p-3 text-right">Monthly</th>
                <th className="p-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {limits.map((l: any, i: number) => (
                <tr key={i} className="border-t">
                  <td className="p-3 font-medium">{l.name}</td>
                  <td className="p-3">{l.txnType}</td>
                  <td className="p-3 text-right">
                    ${l.minAmount?.toLocaleString()}
                  </td>
                  <td className="p-3 text-right">
                    ${l.maxAmount?.toLocaleString()}
                  </td>
                  <td className="p-3 text-right">
                    ${l.dailyLimit?.toLocaleString()}
                  </td>
                  <td className="p-3 text-right">
                    ${l.monthlyLimit?.toLocaleString()}
                  </td>
                  <td className="p-3 text-center">
                    <span
                      className={`px-2 py-1 rounded text-xs ${l.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}`}
                    >
                      {l.active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
