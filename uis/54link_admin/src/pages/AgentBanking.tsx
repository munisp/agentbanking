import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MapPin, TrendingUp, Users, DollarSign, Activity, CheckCircle, XCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

export default function AgentBanking() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const stats = [
    { label: 'Total Agents', value: '1,247', change: '+12%', icon: Users },
    { label: 'Active Today', value: '892', change: '+5%', icon: Activity, color: 'text-green-600' },
    { label: 'Daily Transactions', value: '₦24.5M', change: '+18%', icon: DollarSign, color: 'text-purple-600' },
    { label: 'Commission Paid', value: '₦1.2M', change: '+8%', icon: TrendingUp, color: 'text-orange-600' },
  ];

  const agents = [
    {
      id: 'AGT-001',
      name: 'Adebayo Oluwaseun',
      location: 'Ikeja, Lagos',
      status: 'active',
      transactions: 45,
      volume: 2400000,
      commission: 48000,
      rating: 4.8,
      lastActive: '5 mins ago',
    },
    {
      id: 'AGT-002',
      name: 'Chioma Nwankwo',
      location: 'Aba, Abia',
      status: 'active',
      transactions: 38,
      volume: 1950000,
      commission: 39000,
      rating: 4.9,
      lastActive: '12 mins ago',
    },
    {
      id: 'AGT-003',
      name: 'Musa Ibrahim',
      location: 'Kano, Kano',
      status: 'active',
      transactions: 52,
      volume: 3100000,
      commission: 62000,
      rating: 4.7,
      lastActive: '3 mins ago',
    },
    {
      id: 'AGT-004',
      name: 'Blessing Okon',
      location: 'Port Harcourt, Rivers',
      status: 'inactive',
      transactions: 0,
      volume: 0,
      commission: 0,
      rating: 4.6,
      lastActive: '2 days ago',
    },
  ];

  const transactionData = [
    { service: 'Deposits', count: 450, amount: 12500000 },
    { service: 'Withdrawals', count: 380, amount: 9800000 },
    { service: 'Transfers', count: 220, amount: 1500000 },
    { service: 'Bill Payments', count: 180, amount: 700000 },
  ];

  const performanceData = [
    { name: 'Top 20%', value: 45, color: '#10b981' },
    { name: 'Middle 60%', value: 35, color: primaryColor },
    { name: 'Bottom 20%', value: 20, color: '#ef4444' },
  ];

  const COLORS = ['#10b981', primaryColor, '#ef4444'];

  return (
    <div 
      className="min-h-screen p-6"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`
      }}
    >
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2" style={{ color: primaryColor }}>Agent Banking Network</h1>
          <p className="text-gray-600 dark:text-gray-400">Monitor and manage your agent banking operations</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {stats.map((stat, index) => (
            <Card key={index} className="p-6">
              <div className="flex items-center justify-between mb-2">
                <stat.icon className="h-8 w-8" style={{ color: index === 0 ? primaryColor : undefined }} />
                <Badge className="bg-green-100 text-green-800">{stat.change}</Badge>
              </div>
              <p className="text-sm text-gray-600 mb-1">{stat.label}</p>
              <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
            </Card>
          ))}
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Transaction Volume by Service */}
          <Card className="p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Transaction Volume by Service</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={transactionData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="service" />
                <YAxis />
                <Tooltip formatter={(value: number | undefined) => value !== undefined ? `₦${(value / 1000000).toFixed(1)}M` : ''} />
                <Bar dataKey="amount" fill={primaryColor} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Agent Performance Distribution */}
          <Card className="p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Agent Performance Distribution</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={performanceData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {performanceData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </div>

        {/* Agents Table */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-gray-900">Agent Performance</h2>
            <div className="flex gap-2">
              <Button variant="outline">Export Report</Button>
              <Button style={{ backgroundColor: primaryColor }} className="text-white hover:opacity-90">Onboard New Agent</Button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Agent ID</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Name</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Location</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Transactions</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Volume</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Commission</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Rating</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agent) => (
                  <tr key={agent.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4 font-mono text-sm">{agent.id}</td>
                    <td className="py-3 px-4">
                      <div>
                        <p className="font-medium text-gray-900">{agent.name}</p>
                        <p className="text-sm text-gray-500">{agent.lastActive}</p>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1">
                        <MapPin className="h-4 w-4 text-gray-400" />
                        <span className="text-sm">{agent.location}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge className={agent.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}>
                        {agent.status === 'active' ? (
                          <><CheckCircle className="h-3 w-3 mr-1 inline" />Active</>
                        ) : (
                          <><XCircle className="h-3 w-3 mr-1 inline" />Inactive</>
                        )}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 font-semibold">{agent.transactions}</td>
                    <td className="py-3 px-4">₦{(agent.volume / 1000000).toFixed(1)}M</td>
                    <td className="py-3 px-4">₦{(agent.commission / 1000).toFixed(0)}K</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1">
                        <span className="text-yellow-500">★</span>
                        <span className="font-medium">{agent.rating}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Button variant="outline" size="sm">View Details</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
