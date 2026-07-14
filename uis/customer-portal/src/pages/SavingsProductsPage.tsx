import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PiggyBank, TrendingUp, Users, Calendar } from "lucide-react";

export default function SavingsProductsPage() {
  const [tab, setTab] = useState<"products" | "accounts" | "transactions">(
    "products"
  );
  // @ts-ignore Sprint 85
  const products = trpc.savingsProducts.products.useQuery();
  // @ts-ignore Sprint 85
  const accounts = trpc.savingsProducts.list.useQuery({ limit: 20 });
  // @ts-ignore Sprint 85
  const transactions = trpc.savingsProducts.list.useQuery({ limit: 20 });
  // @ts-ignore Sprint 85
  const analytics = trpc.savingsProducts.analytics.useQuery();

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Savings Products</h1>
          <p className="text-muted-foreground">
            Agent-facilitated savings — daily thrift (ajo/esusu), target
            savings, fixed deposits
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Total Deposits
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                NGN {(analytics.data?.totalDeposits ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Active Accounts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {analytics.data?.activeAccounts ?? 0}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Interest Paid
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                NGN {(analytics.data?.totalInterestPaid ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Active Accounts Savings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {analytics.data?.activeAccounts ?? 0}
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="flex gap-2">
          <Button
            variant={tab === "products" ? "default" : "outline"}
            onClick={() => setTab("products")}
          >
            <PiggyBank className="h-4 w-4 mr-1" />
            Products
          </Button>
          <Button
            variant={tab === "accounts" ? "default" : "outline"}
            onClick={() => setTab("accounts")}
          >
            <Users className="h-4 w-4 mr-1" />
            Accounts
          </Button>
          <Button
            variant={tab === "transactions" ? "default" : "outline"}
            onClick={() => setTab("transactions")}
          >
            <Calendar className="h-4 w-4 mr-1" />
            Transactions
          </Button>
        </div>

        {tab === "products" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {products.data?.products?.map((p: any) => (
              <Card key={p.id}>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-bold">{p.name}</h3>
                    <Badge>{p.type}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mb-3">
                    {p.description}
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">
                        Min Deposit:
                      </span>
                      <p className="font-bold">
                        NGN {p.minDeposit?.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">
                        Interest Rate:
                      </span>
                      <p className="font-bold">{p.interestRate}% p.a.</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">
                        Lock Period:
                      </span>
                      <p className="font-bold">{p.lockPeriod}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Frequency:</span>
                      <p className="font-bold">{p.frequency}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {tab === "accounts" && (
          <Card>
            <CardHeader>
              <CardTitle>Savings Accounts</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Account</th>
                      <th className="text-left p-2">Customer</th>
                      <th className="text-left p-2">Product</th>
                      <th className="text-right p-2">Balance</th>
                      <th className="text-right p-2">Target</th>
                      <th className="text-left p-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.data?.accounts?.map((a: any) => (
                      <tr key={a.id} className="border-b">
                        <td className="p-2 font-mono text-xs">{a.accountNo}</td>
                        <td className="p-2">{a.customerName}</td>
                        <td className="p-2">{a.productName}</td>
                        <td className="p-2 text-right font-bold">
                          NGN {a.balance?.toLocaleString()}
                        </td>
                        <td className="p-2 text-right">
                          NGN {a.targetAmount?.toLocaleString()}
                        </td>
                        <td className="p-2">
                          <Badge
                            variant={
                              a.status === "active" ? "default" : "secondary"
                            }
                          >
                            {a.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {tab === "transactions" && (
          <Card>
            <CardHeader>
              <CardTitle>Recent Transactions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Account</th>
                      <th className="text-left p-2">Type</th>
                      <th className="text-right p-2">Amount</th>
                      <th className="text-left p-2">Agent</th>
                      <th className="text-left p-2">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.data?.accounts?.map((t: any) => (
                      <tr key={t.id} className="border-b">
                        <td className="p-2 font-mono text-xs">{t.accountNo}</td>
                        <td className="p-2">
                          <Badge
                            variant={
                              t.type === "deposit" ? "default" : "secondary"
                            }
                          >
                            {t.type}
                          </Badge>
                        </td>
                        <td className="p-2 text-right font-bold">
                          NGN {t.amount?.toLocaleString()}
                        </td>
                        <td className="p-2">{t.agentName}</td>
                        <td className="p-2 text-xs">
                          {new Date(t.createdAt).toLocaleString()}
                        </td>
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
