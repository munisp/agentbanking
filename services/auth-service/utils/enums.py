import enum


class UserRole(enum.Enum):
    """System-level user roles (Keycloak authentication level)"""

    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class PermifyPlatformRole(enum.Enum):
    """
    v2.perm `platform` entity roles — for 54agent platform-level admins.
    These are assigned on the `platform` Permify entity.
    """

    SUPER_ADMIN = "super_admin"
    TENANT_MANAGER = "tenant_manager"
    OPERATIONS_MANAGER = "operations_manager"
    RISK_MANAGER = "risk_manager"
    INTERNAL_AUDITOR = "internal_auditor"
    IT_ADMIN = "it_admin"
    RELATIONSHIP_MANAGER = "relationship_manager"
    COMPLIANCE_OFFICER = "compliance_officer"
    SUPPORT_AGENT = "support_agent"


class PermifyTenantRole(enum.Enum):
    """
    v2.perm `tenants` entity roles — for bank/tenant-level staff.
    These are assigned on the `tenants` Permify entity.
    """

    SUPER_ADMIN = "super_admin"
    BRANCH_MANAGER = "branch_manager"
    OPERATIONS_MANAGER = "operations_manager"
    RISK_MANAGER = "risk_manager"
    INTERNAL_AUDITOR = "internal_auditor"
    IT_ADMIN = "it_admin"
    RELATIONSHIP_MANAGER = "relationship_manager"
    TRADE_FINANCE_ADMIN = "trade_finance_admin"
    VAULT_MANAGER = "vault_manager"
    TREASURY_MANAGER = "treasury_manager"
    LOAN_OFFICER = "loan_officer"
    COMPLIANCE_OFFICER = "compliance_officer"
    SUPPORT_AGENT = "support_agent"


class PubsubTopics(enum.Enum):
    CORE_54agent_NEW_SUBSCRIBER = "core-54agent-new-subscriber"
    CORE_54agent_NEW_NOTIFICATION = "core-54agent-new-notification"
    CORE_54agent_NEW_ALERT = "core-54agent-new-alert"


class NotificationType(enum.Enum):
    WELCOME_EMAIL = "welcome-email"
    SMS_OTP = "sms-otp"
    EMAIL_OTP = "email-otp"


class NotificationCategory(enum.Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
