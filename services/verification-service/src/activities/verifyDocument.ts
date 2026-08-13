import { NonRetriableApplicationError } from "../middlewares/error";
import { isKycSimulationMode } from "../utils/kycSimulationMode";

/**
 * Verify document authenticity and extract data.
 *
 * FAIL CLOSED: no OCR/document-verification provider is configured in this
 * service. Unless KYC simulation mode is explicitly enabled (non-production
 * only), this activity throws a non-retryable error instead of returning
 * fabricated extraction data, so documents can never be auto-approved.
 */
export async function verifyDocument(args: {
  frontImage: string;
  backImage: string;
  documentType: string;
  country: string;
}): Promise<{
  isValid: boolean;
  extractedData: {
    firstName?: string;
    lastName?: string;
    dateOfBirth?: string;
    documentNumber?: string;
    expiryDate?: string;
    address?: string;
  };
  confidence: number;
}> {
  if (!isKycSimulationMode()) {
    throw new NonRetriableApplicationError(
      "Document verification unavailable: no OCR/document-verification provider is configured for this environment.",
    );
  }

  try {
    // TODO: Integrate with OCR service to extract text from documents
    // TODO: Validate document authenticity (security features, etc.)
    // TODO: Check if document is expired

    // Simulation-mode response only (KYC_SIMULATION_MODE=true, non-production).
    console.log("[SIMULATION] Document verification requested for:", args.documentType, args.country);

    return {
      isValid: true,
      extractedData: {
        firstName: "John",
        lastName: "Doe",
        dateOfBirth: "1990-01-01",
        documentNumber: "ABC123456",
        expiryDate: "2030-01-01",
      },
      confidence: 0.95,
    };
  } catch (error) {
    console.error("Error verifying document:", error);
    return {
      isValid: false,
      extractedData: {},
      confidence: 0,
    };
  }
}
