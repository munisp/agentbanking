import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { FileText, Download, CheckCircle, Clock, AlertTriangle, TrendingUp } from 'lucide-react';
import { useEffect, useState } from 'react';
import apiClient from '../services/api';
import { tenantService } from '../services/tenant';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

interface RegulatoryReport {
  code: string;
  name: string;
  frequency: string;
  lastSubmitted: string;
  nextDue: string;
  status: string;
  autoGenerate: boolean;
}

interface RegulatoryReportsResponse {
  tenant_id: string;
  reports: RegulatoryReport[];
  total: number;
}

export default function RegulatoryReporting() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [reports, setReports] = useState<RegulatoryReport[]>([]);
  const [reportsLoading, setReportsLoading] = useState(true);
  const [reportsTotal, setReportsTotal] = useState(0);

  // Fetch regulatory reports for tenant
  useEffect(() => {
    const fetchRegulatoryReports = async (setLoading = true) => {
      if (setLoading) {
        setReportsLoading(true);
      }
      try {
        const tenantConfig = tenantService.getTenantConfig();
        const tenantId = tenantConfig?.tenant_id || (tenantConfig as any)?.id;
        
        if (!tenantId) {
          console.warn('Tenant ID not available for fetching regulatory reports');
          if (setLoading) {
            setReportsLoading(false);
          }
          return;
        }

        const response = await apiClient.get<RegulatoryReportsResponse>(`/compliance/api/v1/compliance/reports/tenant/${tenantId}`);
        const data = response.data;
        
        // Handle the response structure: { tenant_id, reports: [], total: 0 }
        setReports(Array.isArray(data.reports) ? data.reports : []);
        setReportsTotal(data.total || 0);
      } catch (error) {
        console.error('Error fetching regulatory reports:', error);
        toast.error(error instanceof Error ? error.message : 'Something went wrong. Please try again.');
        if (setLoading) {
          setReports([]);
          setReportsTotal(0);
        }
      } finally {
        if (setLoading) {
          setReportsLoading(false);
        }
      }
    };

    fetchRegulatoryReports(true);
    // Refresh every 30 seconds (silently in background)
    const interval = setInterval(() => fetchRegulatoryReports(false), 30000);
    return () => clearInterval(interval);
  }, []);

  const stats = [
    { label: 'CAR (Min 10%)', value: '15.2%', status: 'compliant', icon: TrendingUp },
    { label: 'Liquidity Ratio (Min 20%)', value: '28.5%', status: 'compliant', icon: TrendingUp },
    { label: 'NPL Ratio (Max 5%)', value: '2.3%', status: 'compliant', icon: TrendingUp },
    { label: 'Reports Due This Month', value: reportsTotal.toString(), status: 'pending', icon: Clock },
  ];

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'compliant':
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="h-3 w-3 mr-1 inline" />Compliant</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-800"><Clock className="h-3 w-3 mr-1 inline" />Pending</Badge>;
      case 'overdue':
        return <Badge className="bg-red-100 text-red-800"><AlertTriangle className="h-3 w-3 mr-1 inline" />Overdue</Badge>;
      case 'current':
        return <Badge style={{ backgroundColor: `${primaryColor}20`, color: primaryColor }}><CheckCircle className="h-3 w-3 mr-1 inline" />Current</Badge>;
      default:
        return <Badge>{status}</Badge>;
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
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2" style={{ color: primaryColor }}>CBN Regulatory Reporting</h1>
          <p className="text-gray-600 dark:text-gray-400">Automated compliance reporting for Central Bank of Nigeria</p>
        </div>

        {/* Compliance Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {stats.map((stat, index) => (
            <Card key={index} className="p-6">
              <div className="flex items-center justify-between mb-2">
                <stat.icon className="h-8 w-8" style={{ color: primaryColor }} />
                {getStatusBadge(stat.status)}
              </div>
              <p className="text-sm text-gray-600 mb-1">{stat.label}</p>
              <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
            </Card>
          ))}
        </div>

        {/* Quick Actions */}
        <Card className="p-6 mb-8">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Quick Actions</h3>
          <div className="flex flex-wrap gap-3">
            <Button style={{ backgroundColor: primaryColor }} className="text-white hover:opacity-90">
              <Download className="h-4 w-4 mr-2" />
              Generate All Pending Reports
            </Button>
            <Button variant="outline">
              <FileText className="h-4 w-4 mr-2" />
              Submit to CBN Portal
            </Button>
            <Button variant="outline">
              <Download className="h-4 w-4 mr-2" />
              Download Compliance Pack
            </Button>
          </div>
        </Card>

        {/* Reports Table */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-gray-900">Regulatory Returns</h2>
            <div className="flex gap-2">
              <Button variant="outline">Filter</Button>
              <Button variant="outline">Export</Button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Code</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Report Name</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Frequency</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Last Submitted</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Next Due</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Auto-Generate</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reportsLoading ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-gray-500">
                      Loading reports...
                    </td>
                  </tr>
                ) : reports.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-gray-500">
                      No regulatory reports found
                    </td>
                  </tr>
                ) : (
                  reports.map((report) => (
                  <tr key={report.code} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4 font-mono text-sm font-semibold">{report.code}</td>
                    <td className="py-3 px-4">
                      <p className="font-medium text-gray-900">{report.name}</p>
                    </td>
                    <td className="py-3 px-4 text-sm">{report.frequency}</td>
                    <td className="py-3 px-4 text-sm">{report.lastSubmitted}</td>
                    <td className="py-3 px-4 text-sm font-medium">{report.nextDue}</td>
                    <td className="py-3 px-4">{getStatusBadge(report.status)}</td>
                    <td className="py-3 px-4">
                      {report.autoGenerate ? (
                        <Badge className="bg-green-100 text-green-800">
                          <CheckCircle className="h-3 w-3 mr-1 inline" />Yes
                        </Badge>
                      ) : (
                        <Badge className="bg-gray-100 text-gray-800">Manual</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm">
                          <Download className="h-3 w-3 mr-1" />
                          Generate
                        </Button>
                        <Button variant="outline" size="sm">View</Button>
                      </div>
                    </td>
                  </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Compliance Notes */}
        <Card 
          className="p-6 mt-8 border"
          style={{
            backgroundColor: `${primaryColor}10`,
            borderColor: `${primaryColor}30`
          }}
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 mt-0.5" style={{ color: primaryColor }} />
            <div>
              <h4 className="font-semibold mb-2" style={{ color: primaryColor }}>Compliance Reminders</h4>
              <ul className="text-sm space-y-1" style={{ color: `${primaryColor}dd` }}>
                <li>• 3 monthly reports due by November 30, 2025</li>
                <li>• Automated generation available for 7 out of 10 reports</li>
                <li>• All ratios currently within CBN compliance thresholds</li>
                <li>• Next quarterly reports due December 31, 2025</li>
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
