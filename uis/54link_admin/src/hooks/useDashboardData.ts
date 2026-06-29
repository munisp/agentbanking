import { useEffect, useState } from "react";
import apiClient from "../services/api";
import { tenantService } from "../services/tenant";

export function useDashboardData() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<{ total_count: number; total_volume: number }>({ total_count: 0, total_volume: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Fetch tenants
        const { tenants: tenantsData } = await tenantService.getAllTenants();
        setTenants(tenantsData);

        // Fetch metrics
        const metricsResponse = await apiClient.get("/ledger/txn/metrics");
        const metricsData = metricsResponse.data;
        if (metricsData?.metrics) {
          setMetrics(metricsData.metrics);
        }

        // Fetch transactions
        const txnResponse = await apiClient.get("/ledger/txn/");
        const txnData = txnResponse.data;
        const txns = Array.isArray(txnData.transactions)
          ? txnData.transactions
          : [];
        setTransactions(txns);

        // Fetch users
        try {
          const userResponse = await apiClient.get("/user/user/tenant");
          const userData = userResponse.data;
          const usersData = Array.isArray(userData)
            ? userData
            : Array.isArray(userData.users)
              ? userData.users
              : Array.isArray(userData.data)
                ? userData.data
                : [];
          setUsers(usersData);
        } catch (error) {
          console.error("Error fetching users:", error);
          setUsers([]);
        }
      } catch (error) {
        console.error("Error fetching dashboard data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  return {
    tenants,
    transactions,
    users,
    metrics,
    loading,
  };
}
