import { NonRetriableApplicationError } from "../middlewares/error";

/**
 * KYC simulation mode gate.
 *
 * The "default"/"liveness" KYC pipelines and their activities are simulated
 * verification flows with no real verification provider behind them. They may
 * only run when simulation mode is explicitly enabled AND the service is not
 * running in production. Every simulated code path must call
 * assertKycSimulationMode() so that, by default, verification fails closed
 * instead of auto-passing users.
 */
export function isKycSimulationMode(): boolean {
  return (
    process.env.KYC_SIMULATION_MODE === "true" &&
    process.env.NODE_ENV !== "production" &&
    process.env.ENVIRONMENT !== "production"
  );
}

/**
 * Throws a non-retryable error when simulated KYC verification is invoked
 * outside simulation mode. Used by mock verification activities so they can
 * never auto-pass a user in a real environment.
 */
export function assertKycSimulationMode(feature: string): void {
  if (!isKycSimulationMode()) {
    throw new NonRetriableApplicationError(
      `${feature} is unavailable: no real verification provider is configured and KYC simulation mode is disabled. ` +
        "Set KYC_SIMULATION_MODE=true in a non-production environment to run simulated verification.",
    );
  }
}
