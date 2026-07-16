import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Users, TrendingUp, AlertCircle, DollarSign } from 'lucide-react';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

export default function GroupLending() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);

  const groups = [
    {
      id: 'GRP-001',
      name: 'Iya Alata Women Cooperative',
      members: 25,
      totalLoan: 5000000,
      disbursed: 5000000,
      repaid: 3200000,
      outstanding: 1800000,
      status: 'active',
      repaymentRate: 94,
      meetingFrequency: 'Weekly',
      nextMeeting: '2025-11-25',
      leader: 'Mrs. Folake Adeyemi',
      guarantors: 3,
    },
    {
      id: 'GRP-002',
      name: 'Agric Farmers Association',
      members: 40,
      totalLoan: 12000000,
      disbursed: 12000000,
      repaid: 8500000,
      outstanding: 3500000,
      status: 'active',
      repaymentRate: 89,
      meetingFrequency: 'Bi-weekly',
      nextMeeting: '2025-11-28',
      leader: 'Mr. Chukwudi Okafor',
      guarantors: 5,
    },
    {
      id: 'GRP-003',
      name: 'Market Traders Union',
      members: 18,
      totalLoan: 3600000,
      disbursed: 3600000,
      repaid: 3600000,
      outstanding: 0,
      status: 'completed',
      repaymentRate: 100,
      meetingFrequency: 'Weekly',
      nextMeeting: '-',
      leader: 'Mrs. Amina Bello',
      guarantors: 2,
    },
    {
      id: 'GRP-004',
      name: 'Youth Entrepreneurs Network',
      members: 15,
      totalLoan: 4500000,
      disbursed: 0,
      repaid: 0,
      outstanding: 4500000,
      status: 'pending',
      repaymentRate: 0,
      meetingFrequency: 'Weekly',
      nextMeeting: '2025-11-26',
      leader: 'Mr. Ibrahim Musa',
      guarantors: 2,
    },
  ];

  const stats = [
    { label: 'Total Groups', value: '124', icon: Users },
    { label: 'Active Loans', value: '₦45.2M', icon: DollarSign },
    { label: 'Avg Repayment Rate', value: '92%', icon: TrendingUp },
    { label: 'Default Rate', value: '2.3%', icon: AlertCircle },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'completed': return 'bg-transparent';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'defaulted': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

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
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2" style={{ color: primaryColor }}>Group Lending Management</h1>
          <p className="text-gray-600 dark:text-gray-400">Manage cooperative groups and track loan performance</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {stats.map((stat, index) => (
            <Card key={index} className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">{stat.label}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                </div>
                <stat.icon className="h-8 w-8" style={{ color: index === 0 ? primaryColor : index === 2 ? secondaryColor : undefined }} />
              </div>
            </Card>
          ))}
        </div>

        {/* Groups Table */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">Active Groups</h2>
            <Button style={{ backgroundColor: primaryColor }} className="text-white hover:opacity-90">Create New Group</Button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Group ID</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Name</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Members</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Total Loan</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Outstanding</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Repayment Rate</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => (
                  <tr key={group.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4 font-mono text-sm">{group.id}</td>
                    <td className="py-3 px-4">
                      <div>
                        <p className="font-medium text-gray-900">{group.name}</p>
                        <p className="text-sm text-gray-500">Leader: {group.leader}</p>
                      </div>
                    </td>
                    <td className="py-3 px-4">{group.members}</td>
                    <td className="py-3 px-4">₦{(group.totalLoan / 1000000).toFixed(1)}M</td>
                    <td className="py-3 px-4">₦{(group.outstanding / 1000000).toFixed(1)}M</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-green-600 h-2 rounded-full"
                            style={{ width: `${group.repaymentRate}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium">{group.repaymentRate}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge 
                        className={getStatusColor(group.status)}
                        style={group.status === 'completed' ? {
                          backgroundColor: `${primaryColor}20`,
                          color: primaryColor
                        } : undefined}
                      >
                        {group.status}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">
                      <Button variant="outline" size="sm" onClick={() => setSelectedGroup(group.id)}>
                        View Details
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Group Details Modal (simplified) */}
        {selectedGroup && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <Card className="max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-2xl font-bold">Group Details</h3>
                <Button variant="outline" onClick={() => setSelectedGroup(null)}>Close</Button>
              </div>
              {groups.find(g => g.id === selectedGroup) && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-gray-600">Group ID</p>
                      <p className="font-semibold">{groups.find(g => g.id === selectedGroup)?.id}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Members</p>
                      <p className="font-semibold">{groups.find(g => g.id === selectedGroup)?.members}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Meeting Frequency</p>
                      <p className="font-semibold">{groups.find(g => g.id === selectedGroup)?.meetingFrequency}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Next Meeting</p>
                      <p className="font-semibold">{groups.find(g => g.id === selectedGroup)?.nextMeeting}</p>
                    </div>
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
