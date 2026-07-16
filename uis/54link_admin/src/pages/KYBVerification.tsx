import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle, AlertCircle } from "lucide-react";
import { Button } from "../components/ui/button";
import { Alert, AlertDescription } from "../components/ui/alert";
import { KYBVerificationForm } from "../components/KYBVerificationForm";

export default function KYBVerification() {
  const navigate = useNavigate();
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSuccess = (verificationId: string) => {
    setSuccess(
      `KYB verification started successfully! Verification ID: ${verificationId}`,
    );
    setError(null);
    // Auto-clear success message after 5 seconds
    setTimeout(() => setSuccess(null), 5000);
  };

  const handleError = (errorMessage: string) => {
    setError(errorMessage);
    setSuccess(null);
  };

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl">
      <div className="mb-6">
        <Button
          variant="ghost"
          onClick={() => navigate(-1)}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>

        <h1 className="text-3xl font-bold mb-2">KYB Verification</h1>
        <p className="text-muted-foreground">
          Verify business information and upload required documents
        </p>
      </div>

      {success && (
        <Alert className="mb-6 border-green-500 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            {success}
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <KYBVerificationForm onSuccess={handleSuccess} onError={handleError} />
    </div>
  );
}
