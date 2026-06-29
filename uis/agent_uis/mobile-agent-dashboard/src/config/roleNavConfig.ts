/**
 * Role-based navigation configuration for 54agent mobile
 * Mirrors the PWA 7-role PBAC hierarchy
 */

export type UserRole =
  | 'super_admin'
  | 'admin'
  | 'supervisor'
  | 'agent_manager'
  | 'agent'
  | 'auditor'
  | 'viewer';

export const ROLE_LEVEL: Record<UserRole, number> = {
  super_admin: 7,
  admin: 6,
  supervisor: 5,
  agent_manager: 4,
  agent: 3,
  auditor: 2,
  viewer: 1,
};

export const GROUP_MIN_LEVEL: Record<string, number> = {
  core: 1,
  help: 1,
  analytics: 2,
  finance: 3,
  notifications: 3,
  engagement: 3,
  ecommerce: 3,
  agents: 4,
  portals: 4,
  admin: 5,
  infra: 6,
  integrations: 6,
  tenant: 6,
  'ai-ml': 6,
  'data-pipelines': 6,
  'production-ops': 6,
  enterprise: 6,
  'financial-services': 3,
  'agency-banking': 3,
  billing: 6,
  future: 7,
};

export function parseRole(role?: string): UserRole {
  if (!role) return 'viewer';
  const mapped: Record<string, UserRole> = {
    super_admin: 'super_admin',
    admin: 'admin',
    supervisor: 'supervisor',
    agent_manager: 'agent_manager',
    agent: 'agent',
    auditor: 'auditor',
    viewer: 'viewer',
  };
  return mapped[role] || 'viewer';
}

export function canAccessGroup(role: UserRole, groupId: string): boolean {
  const level = ROLE_LEVEL[role] || 1;
  const minLevel = GROUP_MIN_LEVEL[groupId] || 7;
  return level >= minLevel;
}

export function getRoleDisplayName(role: UserRole): string {
  const names: Record<UserRole, string> = {
    super_admin: 'Super Admin',
    admin: 'Admin',
    supervisor: 'Supervisor',
    agent_manager: 'Agent Manager',
    agent: 'Agent',
    auditor: 'Auditor',
    viewer: 'Viewer',
  };
  return names[role] || 'Viewer';
}
