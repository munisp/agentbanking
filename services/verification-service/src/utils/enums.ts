export enum CustomerStatuses {
  onboarding = "onboarding",
  during_pilot = "during_pilot",
  active = "active",
  terminated = "terminated",
}

export enum VerificationWorkflowStatus {
  NOT_STARTED = "not-started",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum KycIdentityProviders {
  SHIELD = "shield",
  MOSIP = "mosip",
  DEFAULT = "default",
  LIVENESS = "liveness",
}

export enum KycVerificationImageTypeEnum {
  FACE = "face",
  ID_CARD = "id_card",
  DRIVERS_LICENSE = "drivers_license",
}
