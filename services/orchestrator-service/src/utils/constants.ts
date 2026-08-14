export enum PubsubTopics {
  NEW_SUBSCRIBER = "54agent-new-subscriber",
  UPDATE_SUBSCRIBER = "54agent-update-subscriber",
  NEW_NOTIFICATION = "54agent-new-notification",
  NEW_AUDIT = "54agent-audit",
}
// SEC-10: DEFAULT_ADMIN_PASSWORD ("Admin12345!") was removed. Hard-coded
// fallback credentials are never acceptable. Callers must supply a password
// explicitly or set the ADMIN_INITIAL_PASSWORD environment variable on the
// orchestrator service; createAdminWorkflow fails closed when neither exists.
