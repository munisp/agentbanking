import { useState } from "react";
import { Upload, X, FileText, CheckCircle, AlertCircle } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { kybService } from "../services/kybService";
import { tenantService } from "../services/tenant/tenantService";
import type {
  KYBDocument,
  KYBVerificationRequest,
  DocumentType,
} from "../types/kyb";

interface DocumentUpload {
  type: DocumentType;
  file: File | null;
  url: string;
  uploading: boolean;
  uploaded: boolean;
  error?: string;
}

interface KYBVerificationFormProps {
  onSuccess?: (verificationId: string) => void;
  onError?: (error: string) => void;
}

const DOCUMENT_TYPES: { value: DocumentType; label: string }[] = [
  { value: "certificate_of_incorporation", label: "Certificate of Incorporation" },
  { value: "tax_identification_number", label: "Tax Identification Number" },
  { value: "business_license", label: "Business License" },
  { value: "utility_bill", label: "Utility Bill" },
  { value: "bank_statement", label: "Bank Statement" },
  { value: "memorandum_of_association", label: "Memorandum of Association" },
  { value: "articles_of_association", label: "Articles of Association" },
  { value: "director_id", label: "Director ID" },
  { value: "shareholder_id", label: "Shareholder ID" },
];

const VERIFICATION_PATHS = [
  { value: "sme_kyc_standard", label: "SME KYC Standard" },
  { value: "sme_kyc_enhanced", label: "SME KYC Enhanced" },
  { value: "corporate_kyc_standard", label: "Corporate KYC Standard" },
  { value: "corporate_kyc_enhanced", label: "Corporate KYC Enhanced" },
];

const PRIORITY_LEVELS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

export function KYBVerificationForm({
  onSuccess,
  onError,
}: KYBVerificationFormProps) {
  const [businessId, setBusinessId] = useState("");
  const [verificationPath, setVerificationPath] = useState("sme_kyc_standard");
  const [timeoutDays, setTimeoutDays] = useState(30);
  const [priority, setPriority] = useState<"low" | "medium" | "high">("medium");
  const [country, setCountry] = useState("NG");
  const [requestedBy, setRequestedBy] = useState("");
  const [documents, setDocuments] = useState<DocumentUpload[]>([
    {
      type: "certificate_of_incorporation",
      file: null,
      url: "",
      uploading: false,
      uploaded: false,
    },
    {
      type: "tax_identification_number",
      file: null,
      url: "",
      uploading: false,
      uploaded: false,
    },
  ]);
  const [submitting, setSubmitting] = useState(false);

  const addDocument = () => {
    setDocuments([
      ...documents,
      {
        type: "business_license",
        file: null,
        url: "",
        uploading: false,
        uploaded: false,
      },
    ]);
  };

  const removeDocument = (index: number) => {
    setDocuments(documents.filter((_, i) => i !== index));
  };

  const updateDocumentType = (index: number, type: DocumentType) => {
    const newDocs = [...documents];
    newDocs[index].type = type;
    setDocuments(newDocs);
  };

  const handleFileChange = async (index: number, file: File | null) => {
    if (!file) return;

    const newDocs = [...documents];
    newDocs[index].file = file;
    newDocs[index].uploading = true;
    newDocs[index].error = undefined;
    setDocuments(newDocs);

    try {
      const response = await kybService.uploadDocument(file, newDocs[index].type);
      newDocs[index].url = response.url;
      newDocs[index].uploaded = true;
      newDocs[index].uploading = false;
      setDocuments([...newDocs]);
    } catch (error) {
      newDocs[index].uploading = false;
      newDocs[index].error =
        error instanceof Error ? error.message : "Upload failed";
      setDocuments([...newDocs]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!businessId.trim()) {
      onError?.("Business ID is required");
      return;
    }

    if (!requestedBy.trim()) {
      onError?.("Requested by is required");
      return;
    }

    const uploadedDocs = documents.filter((doc) => doc.uploaded);
    if (uploadedDocs.length === 0) {
      onError?.("At least one document must be uploaded");
      return;
    }

    setSubmitting(true);

    try {
      const tenant = tenantService.getTenantConfig();
      const verificationId = kybService.generateVerificationId();

      const payload: KYBVerificationRequest = {
        verification_id: verificationId,
        tenant_id: tenant?.tenant_id || "bpmgd",
        business_id: businessId,
        verification_path: verificationPath,
        required_documents: documents.map((doc) => doc.type),
        uploaded_documents: uploadedDocs.map(
          (doc): KYBDocument => ({
            title: doc.type,
            url: doc.url,
          }),
        ),
        timeout_days: timeoutDays,
        metadata: {
          requested_by: requestedBy,
          source: "backoffice",
          priority: priority,
          country: country,
        },
      };

      const response = await kybService.startVerification(payload);
      onSuccess?.(response.verification_id);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Verification failed";
      onError?.(errorMessage);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Business Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="businessId">Business ID *</Label>
            <Input
              id="businessId"
              value={businessId}
              onChange={(e) => setBusinessId(e.target.value)}
              placeholder="biz_78910"
              required
            />
          </div>

          <div>
            <Label htmlFor="verificationPath">Verification Path *</Label>
            <Select value={verificationPath} onValueChange={setVerificationPath}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {VERIFICATION_PATHS.map((path) => (
                  <SelectItem key={path.value} value={path.value}>
                    {path.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="timeoutDays">Timeout (Days)</Label>
              <Input
                id="timeoutDays"
                type="number"
                value={timeoutDays}
                onChange={(e) => setTimeoutDays(Number(e.target.value))}
                min={1}
                max={365}
              />
            </div>

            <div>
              <Label htmlFor="country">Country</Label>
              <Input
                id="country"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="NG"
                maxLength={2}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="requestedBy">Requested By *</Label>
            <Input
              id="requestedBy"
              value={requestedBy}
              onChange={(e) => setRequestedBy(e.target.value)}
              placeholder="admin_user_42"
              required
            />
          </div>

          <div>
            <Label htmlFor="priority">Priority</Label>
            <Select
              value={priority}
              onValueChange={(value) =>
                setPriority(value as "low" | "medium" | "high")
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PRIORITY_LEVELS.map((level) => (
                  <SelectItem key={level.value} value={level.value}>
                    {level.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {documents.map((doc, index) => (
            <div
              key={index}
              className="border rounded-lg p-4 space-y-3 relative"
            >
              {documents.length > 2 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute top-2 right-2"
                  onClick={() => removeDocument(index)}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}

              <div>
                <Label>Document Type</Label>
                <Select
                  value={doc.type}
                  onValueChange={(value) =>
                    updateDocumentType(index, value as DocumentType)
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DOCUMENT_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Upload File</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type="file"
                    onChange={(e) =>
                      handleFileChange(index, e.target.files?.[0] || null)
                    }
                    disabled={doc.uploading}
                    accept=".pdf,.jpg,.jpeg,.png"
                  />
                  {doc.uploading && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary" />
                      Uploading...
                    </div>
                  )}
                  {doc.uploaded && (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  )}
                  {doc.error && (
                    <AlertCircle className="h-5 w-5 text-destructive" />
                  )}
                </div>
                {doc.error && (
                  <p className="text-sm text-destructive mt-1">{doc.error}</p>
                )}
                {doc.uploaded && doc.url && (
                  <div className="flex items-center gap-2 mt-2 text-sm text-muted-foreground">
                    <FileText className="h-4 w-4" />
                    <span className="truncate">{doc.file?.name}</span>
                  </div>
                )}
              </div>
            </div>
          ))}

          <Button
            type="button"
            variant="outline"
            onClick={addDocument}
            className="w-full"
          >
            <Upload className="h-4 w-4 mr-2" />
            Add Another Document
          </Button>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-4">
        <Button
          type="submit"
          disabled={
            submitting ||
            documents.filter((doc) => doc.uploaded).length === 0
          }
        >
          {submitting ? "Submitting..." : "Start Verification"}
        </Button>
      </div>
    </form>
  );
}
