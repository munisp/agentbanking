// Design philosophy: restored original banking PWA shell.
// This provider gives the recovered customer experience a durable session identity,
// persisted notifications, and a single active customer anchor across all mobile routes.

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getCustomerDashboardPayload, getCustomerSettingsPayload, type CustomerExperienceCustomer, type CustomerExperienceWorkflow } from "@/lib/customerExperienceData";
import {
  createCustomerNotification,
  getCustomerNotifications,
  getCustomerSessionPreference,
  updateCustomerNotification,
  updateCustomerSessionPreference,
  type AuditEntry,
  type AuthContextResponse,
  type CustomerNotificationRecord as CustomerNotification,
  type TenantConfiguration,
} from "@/lib/platform";

interface CustomerSessionContextValue {
  loading: boolean;
  error: string | null;
  customers: CustomerExperienceCustomer[];
  activeCustomer: CustomerExperienceCustomer | null;
  workflows: CustomerExperienceWorkflow[];
  audits: AuditEntry[];
  authContext: AuthContextResponse | null;
  tenantConfiguration: TenantConfiguration | null;
  notifications: CustomerNotification[];
  unreadNotifications: number;
  switchCustomer: (customerId: string) => void;
  markNotificationAsRead: (notificationId: string) => void;
  markAllNotificationsAsRead: () => void;
  addNotification: (notification: Omit<CustomerNotification, "id" | "createdAt" | "read" | "customerId">) => void;
}

const CustomerSessionContext = createContext<CustomerSessionContextValue | null>(null);

export function CustomerSessionProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [customers, setCustomers] = useState<CustomerExperienceCustomer[]>([]);
  const [workflows, setWorkflows] = useState<CustomerExperienceWorkflow[]>([]);
  const [audits, setAudits] = useState<AuditEntry[]>([]);
  const [authContext, setAuthContext] = useState<AuthContextResponse | null>(null);
  const [tenantConfiguration, setTenantConfiguration] = useState<TenantConfiguration | null>(null);
  const [activeCustomerId, setActiveCustomerIdState] = useState<string | null>(null);
  const [notifications, setNotificationsState] = useState<CustomerNotification[]>([]);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const [dashboardPayload, settingsPayload] = await Promise.all([getCustomerDashboardPayload(), getCustomerSettingsPayload()]);
        if (!active) return;

        const customerList = dashboardPayload.customers;
        const resolvedAuthContext = settingsPayload.authContext as AuthContextResponse;
        const resolvedTenantConfiguration = (settingsPayload.tenantConfiguration ?? dashboardPayload.tenantConfiguration ?? null) as TenantConfiguration | null;
        const defaultCustomerId = customerList[0]?.id ?? null;
        const persistedPreference = await getCustomerSessionPreference(
          resolvedAuthContext.role,
          resolvedAuthContext.actorId,
          resolvedAuthContext.tenantId,
        ).catch(() => null);
        const preferredCustomerId =
          persistedPreference?.activeCustomerId && customerList.some((customer) => customer.id === persistedPreference.activeCustomerId)
            ? persistedPreference.activeCustomerId
            : defaultCustomerId;
        const notificationResponse = preferredCustomerId
          ? await getCustomerNotifications(preferredCustomerId).catch(() => ({ items: [] as CustomerNotification[] }))
          : { items: [] as CustomerNotification[] };

        setCustomers(customerList);
        setWorkflows(dashboardPayload.workflows);
        setAudits(dashboardPayload.audits as AuditEntry[]);
        setAuthContext(resolvedAuthContext);
        setTenantConfiguration(resolvedTenantConfiguration);
        setActiveCustomerIdState(preferredCustomerId);
        setNotificationsState(notificationResponse.items);
        setError(null);
      } catch (issue) {
        if (!active) return;
        setError(issue instanceof Error ? issue.message : "Unable to initialize the customer session.");
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const activeCustomer = useMemo(
    () => customers.find((customer) => customer.id === activeCustomerId) ?? customers[0] ?? null,
    [activeCustomerId, customers],
  );

  useEffect(() => {
    if (!activeCustomer) return;
    let active = true;
    void getCustomerNotifications(activeCustomer.id)
      .then((response) => {
        if (active) setNotificationsState(response.items);
      })
      .catch(() => {
        if (active) setNotificationsState([]);
      });
    return () => {
      active = false;
    };
  }, [activeCustomer?.id]);

  const value = useMemo<CustomerSessionContextValue>(
    () => ({
      loading,
      error,
      customers,
      activeCustomer,
      workflows,
      audits,
      authContext,
      tenantConfiguration,
      notifications,
      unreadNotifications: notifications.filter((notification) => !notification.read).length,
      switchCustomer: (customerId: string) => {
        const previousCustomerId = activeCustomer?.id ?? customers[0]?.id ?? null;
        setActiveCustomerIdState(customerId);
        if (authContext) {
          void updateCustomerSessionPreference(
            { activeCustomerId: customerId },
            authContext.role,
            authContext.actorId,
            authContext.tenantId,
          ).catch(() => {
            setActiveCustomerIdState(previousCustomerId);
          });
        }
      },
      markNotificationAsRead: (notificationId: string) => {
        const next = notifications.map((notification) =>
          notification.id === notificationId ? { ...notification, read: true } : notification,
        );
        setNotificationsState(next);
        void updateCustomerNotification(notificationId, { read: true }).catch(() => {
          setNotificationsState(notifications);
        });
      },
      markAllNotificationsAsRead: () => {
        const next = notifications.map((notification) => ({ ...notification, read: true }));
        setNotificationsState(next);
        void Promise.all(next.map((notification) => updateCustomerNotification(notification.id, { read: true }).catch(() => null)));
      },
      addNotification: (notification) => {
        const optimistic: CustomerNotification = {
          ...notification,
          id: `notification-${Date.now()}`,
          customerId: activeCustomer?.id ?? customers[0]?.id ?? "CUS-001",
          createdAt: new Date().toISOString(),
          read: false,
        };
        setNotificationsState([optimistic, ...notifications].slice(0, 50));
        void createCustomerNotification(optimistic)
          .then((created) => {
            setNotificationsState((current) => [created, ...current.filter((item) => item.id !== optimistic.id)].slice(0, 50));
          })
          .catch(() => {
            setNotificationsState((current) => current.filter((item) => item.id !== optimistic.id));
          });
      },
    }),
    [activeCustomer, audits, authContext, customers, error, loading, notifications, tenantConfiguration, workflows],
  );

  return <CustomerSessionContext.Provider value={value}>{children}</CustomerSessionContext.Provider>;
}

export function useCustomerSession() {
  const context = useContext(CustomerSessionContext);
  if (!context) {
    throw new Error("useCustomerSession must be used within CustomerSessionProvider.");
  }
  return context;
}
