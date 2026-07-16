export const API_ENDPOINTS = {
  AUTH: {
    LOGIN: "/auth/login",
    SIGNUP: "/auth/signup",
    LOGOUT: "/auth/logout",
    VALIDATE: "/auth/validate",
    RESET_PASSWORD: "/auth/reset-password",
  },
  TRANSACTIONS: {
    LIST: "/transactions",
    DETAILS: "/transactions/:id",
    CREATE: "/transactions",
    RECEIPT: "/transactions/:id/receipt",
  },
  POS: {
    LIST: "/pos/terminals",
    DETAILS: "/pos/terminals/:id",
    ORDER: "/pos/orders",
    REQUESTS: "/pos/requests",
  },
  FLOAT: {
    BALANCE: "/float/balance",
    REQUEST: "/float/request",
    HISTORY: "/float/history",
  },
  DASHBOARD: {
    STATS: "/dashboard/stats",
    ACTIVITIES: "/dashboard/activities",
  },
};

export const TRANSACTION_TYPES = {
  TRANSFER: "transfer",
  BILL_PAYMENT: "bill_payment",
  FLOAT_REQUEST: "float_request",
  WITHDRAWAL: "withdrawal",
  DEPOSIT: "deposit",
};

export const TRANSACTION_STATUS = {
  COMPLETED: "completed",
  PENDING: "pending",
  FAILED: "failed",
  CANCELLED: "cancelled",
};

export const POS_STATUS = {
  ACTIVE: "active",
  INACTIVE: "inactive",
  MAINTENANCE: "maintenance",
  SUSPENDED: "suspended",
};
