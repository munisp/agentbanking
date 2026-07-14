import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Activity, ArrowDownRight, ArrowUpRight, BarChart3, DollarSign, TrendingUp, Users } from "lucide-react";
import { useState } from "react";
import { CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useTenantBranding } from '../../../contexts/TenantBrandingContext';

export default function AdminAnalytics() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [timeRange, setTimeRange] = useState('6m');
  
  // Empty data arrays - to be populated from API
  const performanceData: Array<{ month: string; transactions: number; revenue: number; users: number }> = [];
  const channelData: Array<{ name: string; value: number; color: string }> = [];
  const productData: Array<{ product: string; customers: number; growth: string }> = [];

  return (
    <div 
      className="min-h-screen dark:from-slate-900 dark:via-slate-900 dark:to-slate-900"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`
      }}
    >
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                <BarChart3 className="w-8 h-8" style={{ color: primaryColor }} />
                Admin Analytics
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                Comprehensive banking analytics and insights
              </p>
            </div>
            <Tabs value={timeRange} onValueChange={setTimeRange}>
              <TabsList>
                <TabsTrigger value="1m">1M</TabsTrigger>
                <TabsTrigger value="3m">3M</TabsTrigger>
                <TabsTrigger value="6m">6M</TabsTrigger>
                <TabsTrigger value="1y">1Y</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>
      </div>

      <div className="container py-8 space-y-8">
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Transactions</CardTitle>
              <Activity className="w-4 h-4" style={{ color: primaryColor }} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">0</div>
              <p className="text-xs text-green-600 flex items-center gap-1 mt-1">
                <ArrowUpRight className="w-3 h-3" />
                No data available
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
              <DollarSign className="w-4 h-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">₦0</div>
              <p className="text-xs text-green-600 flex items-center gap-1 mt-1">
                <ArrowUpRight className="w-3 h-3" />
                No data available
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Active Users</CardTitle>
              <Users className="w-4 h-4 text-purple-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">0</div>
              <p className="text-xs text-green-600 flex items-center gap-1 mt-1">
                <ArrowUpRight className="w-3 h-3" />
                No data available
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Avg. Transaction Value</CardTitle>
              <TrendingUp className="w-4 h-4 text-orange-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">₦0</div>
              <p className="text-xs text-red-600 flex items-center gap-1 mt-1">
                <ArrowDownRight className="w-3 h-3" />
                No data available
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Performance Trends */}
        <Card>
          <CardHeader>
            <CardTitle>Performance Trends</CardTitle>
            <CardDescription>6-month performance overview</CardDescription>
          </CardHeader>
          <CardContent>
            {performanceData.length === 0 ? (
              <div className="flex items-center justify-center h-[350px] text-slate-500">
                No performance data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={350}>
                <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="month" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px'
                  }} 
                />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="transactions" 
                  stroke={primaryColor} 
                  strokeWidth={2}
                  name="Transactions"
                />
                <Line 
                  type="monotone" 
                  dataKey="revenue" 
                  stroke={secondaryColor} 
                  strokeWidth={2}
                  name="Revenue (₦)"
                />
                <Line 
                  type="monotone" 
                  dataKey="users" 
                  stroke="#10b981" 
                  strokeWidth={2}
                  name="Active Users"
                />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Channel Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>Transaction Channels</CardTitle>
              <CardDescription>Distribution by channel type</CardDescription>
            </CardHeader>
            <CardContent>
              {channelData.length === 0 ? (
                <div className="flex items-center justify-center h-[300px] text-slate-500">
                  No channel data available
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={channelData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={(props: any) => props.percent !== undefined ? `${props.name}: ${(props.percent * 100).toFixed(0)}%` : props.name}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {channelData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Product Performance */}
          <Card>
            <CardHeader>
              <CardTitle>Product Performance</CardTitle>
              <CardDescription>Customer distribution by product</CardDescription>
            </CardHeader>
            <CardContent>
              {productData.length === 0 ? (
                <div className="flex items-center justify-center h-[300px] text-slate-500">
                  No product data available
                </div>
              ) : (
                <div className="space-y-4">
                  {productData.map((item) => (
                    <div key={item.product} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: primaryColor }}></div>
                        <span className="font-medium text-slate-900 dark:text-white">
                          {item.product}
                        </span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-slate-600 dark:text-slate-400">
                          {item.customers.toLocaleString()}
                        </span>
                        <span className="text-green-600 text-sm font-medium">
                          {item.growth}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
