import enum


class AgentRole(enum.Enum):
    AGENT = "agent"
    SUPER_AGENT = "super_agent"
    AGGREGATOR = "aggregator"


class AgentStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INVITED = "invited"
    SUSPENDED = "suspended"
    PENDING_APPROVAL = "pending_approval"


class AgentOnboardingStatus(enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


class KycVerificationStatus(enum.Enum):
    NOT_VERIFIED = "not_verified"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED_VERIFICATION = "failed_verification"


class AgentEventTypes(enum.Enum):
    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_APPROVED = "agent.approved"
    AGENT_SUSPENDED = "agent.suspended"
    AGENT_ONBOARDING_COMPLETED = "agent.onboarding.completed"
