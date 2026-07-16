/// Role-based navigation configuration for 54Link mobile
/// Mirrors the PWA 7-role PBAC hierarchy

enum UserRole {
  superAdmin,
  admin,
  supervisor,
  agentManager,
  agent,
  auditor,
  viewer,
}

UserRole parseRole(String? role) {
  switch (role) {
    case 'super_admin':
      return UserRole.superAdmin;
    case 'admin':
      return UserRole.admin;
    case 'supervisor':
      return UserRole.supervisor;
    case 'agent_manager':
      return UserRole.agentManager;
    case 'agent':
      return UserRole.agent;
    case 'auditor':
      return UserRole.auditor;
    default:
      return UserRole.viewer;
  }
}

int roleLevel(UserRole role) {
  switch (role) {
    case UserRole.superAdmin:
      return 7;
    case UserRole.admin:
      return 6;
    case UserRole.supervisor:
      return 5;
    case UserRole.agentManager:
      return 4;
    case UserRole.agent:
      return 3;
    case UserRole.auditor:
      return 2;
    case UserRole.viewer:
      return 1;
  }
}

/// Minimum role level required for each nav group
const Map<String, int> groupMinLevel = {
  'core': 1,
  'help': 1,
  'analytics': 2,
  'finance': 3,
  'notifications': 3,
  'engagement': 3,
  'ecommerce': 3,
  'agents': 4,
  'portals': 4,
  'admin': 5,
  'infra': 6,
  'integrations': 6,
  'tenant': 6,
  'ai-ml': 6,
  'data-pipelines': 6,
  'production-ops': 6,
  'enterprise': 6,
  'financial-services': 3,
  'agency-banking': 3,
  'billing': 6,
  'future': 7,
};

bool canAccessGroup(UserRole role, String groupId) {
  final level = roleLevel(role);
  final minLevel = groupMinLevel[groupId] ?? 7;
  return level >= minLevel;
}
