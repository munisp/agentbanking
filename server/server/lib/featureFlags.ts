/**
 * Feature Flags — centralized feature toggle management
 *
 * Supports: boolean flags, percentage rollouts, user/tenant targeting,
 * environment-based overrides, A/B testing variants.
 */

interface FeatureFlag {
  name: string;
  enabled: boolean;
  rolloutPercent: number;
  description: string;
  targetTenants?: number[];
  targetRoles?: string[];
  variants?: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

const DEFAULT_FLAGS: Record<string, FeatureFlag> = {
  ai_chatbot: {
    name: "ai_chatbot",
    enabled: true,
    rolloutPercent: 100,
    description: "AI-powered agent support chatbot",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  predictive_float: {
    name: "predictive_float",
    enabled: true,
    rolloutPercent: 50,
    description: "Predictive float depletion alerts",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  whatsapp_banking: {
    name: "whatsapp_banking",
    enabled: false,
    rolloutPercent: 0,
    description: "WhatsApp conversational banking channel",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  gamification: {
    name: "gamification",
    enabled: true,
    rolloutPercent: 100,
    description: "Agent leaderboards and achievements",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  dark_mode: {
    name: "dark_mode",
    enabled: true,
    rolloutPercent: 100,
    description: "Dark mode UI theme",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  cursor_pagination: {
    name: "cursor_pagination",
    enabled: false,
    rolloutPercent: 10,
    description: "Cursor-based pagination for high-volume endpoints",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  cross_border: {
    name: "cross_border",
    enabled: false,
    rolloutPercent: 0,
    description: "Cross-border ECOWAS remittance corridors",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  biometric_auth: {
    name: "biometric_auth",
    enabled: true,
    rolloutPercent: 100,
    description: "Biometric authentication for agents (fingerprint, face)",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  geofencing: {
    name: "geofencing",
    enabled: true,
    rolloutPercent: 100,
    description: "POS geofencing and location-based services",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
  micro_insurance: {
    name: "micro_insurance",
    enabled: false,
    rolloutPercent: 0,
    description: "Embedded micro-insurance products",
    createdAt: "2026-01-01",
    updatedAt: "2026-06-01",
  },
};

// In-memory store (production: Redis or DB-backed)
let flags: Record<string, FeatureFlag> = { ...DEFAULT_FLAGS };

export function isFeatureEnabled(
  flagName: string,
  context?: { userId?: number; tenantId?: number; role?: string }
): boolean {
  const flag = flags[flagName];
  if (!flag) return false;
  if (!flag.enabled) return false;

  // Tenant targeting
  if (flag.targetTenants?.length && context?.tenantId) {
    if (!flag.targetTenants.includes(context.tenantId)) return false;
  }

  // Role targeting
  if (flag.targetRoles?.length && context?.role) {
    if (!flag.targetRoles.includes(context.role)) return false;
  }

  // Percentage rollout
  if (flag.rolloutPercent < 100) {
    const hash = context?.userId
      ? (context.userId * 2654435761) % 100
      : Date.now() % 100;
    return hash < flag.rolloutPercent;
  }

  return true;
}

export function setFlag(name: string, updates: Partial<FeatureFlag>) {
  if (!flags[name]) {
    flags[name] = {
      name,
      enabled: false,
      rolloutPercent: 0,
      description: "",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      ...updates,
    };
  } else {
    flags[name] = {
      ...flags[name],
      ...updates,
      updatedAt: new Date().toISOString(),
    };
  }
}

export function getAllFlags(): Record<string, FeatureFlag> {
  return { ...flags };
}

export function getFlag(name: string): FeatureFlag | undefined {
  return flags[name];
}

export function getAllDefaultFlags(): Array<{ key: string } & FeatureFlag> {
  return Object.entries(DEFAULT_FLAGS).map(([key, flag]) => ({
    key,
    ...flag,
  }));
}
