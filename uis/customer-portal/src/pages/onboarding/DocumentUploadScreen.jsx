import {
    AlertCircle,
    ArrowLeft,
    CheckCircle,
    Eye,
    FileText,
    Upload,
    X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import OnboardingProgressIndicator from "../../components/OnboardingProgressIndicator.jsx";
import { storage } from "../../utils/storage.js";

const DocumentUploadScreen = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [accountType, setAccountType] = useState("");
  const [uploadedDocs, setUploadedDocs] = useState({
    passport: { uploaded: false, file: null, fileName: null },
    nin: { uploaded: false, file: null, fileName: null },
    driversLicense: { uploaded: false, file: null, fileName: null },
    cac: { uploaded: false, file: null, fileName: null },
  });

  useEffect(() => {
    // Get account type from state or storage
    const type = location.state?.accountType || storage.getAccountType();
    setAccountType(type);

    // Load previously uploaded documents if exists
    const savedData = storage.getOnboardingData();
    if (savedData?.documents) {
      setUploadedDocs(savedData.documents);
    }
  }, [location]);

  const documentTypes = [
    {
      key: "passport",
      title: "International Passport",
      description: "Valid international passport",
      required: false,
    },
    {
      key: "nin",
      title: "National Identity Number (NIN)",
      description: "NIN slip or card",
      required: false,
    },
    {
      key: "driversLicense",
      title: "Driver's License",
      description: "Valid driver license",
      required: false,
    },
  ];

  // Add CAC for business accounts
  if (accountType === "business") {
    documentTypes.push({
      key: "cac",
      title: "CAC Certificate",
      description: "Certificate of Incorporation",
      required: true,
    });
  }

  const handleFileUpload = (key) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*,.pdf";
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (file) {
        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
          alert("File size must be less than 5MB");
          return;
        }

        setUploadedDocs({
          ...uploadedDocs,
          [key]: {
            uploaded: true,
            file: file,
            fileName: file.name,
          },
        });
      }
    };
    input.click();
  };

  const handleRemoveDocument = (key) => {
    setUploadedDocs({
      ...uploadedDocs,
      [key]: { uploaded: false, file: null, fileName: null },
    });
  };

  const handleContinue = async () => {
    // Check if at least one document is uploaded
    const hasUploadedDocs = Object.values(uploadedDocs).some(
      (doc) => doc.uploaded,
    );

    if (!hasUploadedDocs) {
      alert("Please upload at least one identity document");
      return;
    }

    // For business accounts, CAC is required
    if (accountType === "business" && !uploadedDocs.cac.uploaded) {
      alert("CAC Certificate is required for business accounts");
      return;
    }

    // Save documents to localStorage
    const onboardingData = storage.getOnboardingData() || {};
    const updatedData = {
      ...onboardingData,
      documents: uploadedDocs,
      accountType,
    };
    storage.saveOnboardingData(updatedData);

    // Navigate to completion screen
    navigate("/onboarding/completion", {
      state: { accountType },
    });
  };

  const handleBack = () => {
    navigate("/onboarding/address-verification");
  };

  const hasUploadedDocs = Object.values(uploadedDocs).some(
    (doc) => doc.uploaded,
  );

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4">
      <div className="max-w-2xl w-full space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 bg-green-600 rounded-2xl flex items-center justify-center shadow-lg">
              <FileText className="text-white w-8 h-8" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">
            Upload Identity Documents
          </h1>
          <p className="text-gray-600 mt-2">
            Upload at least one valid ID for CBN compliance
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <OnboardingProgressIndicator currentStep={5} totalSteps={5} />
        </div>

        {/* Info Banner */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
          <div className="flex gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-yellow-900 font-medium mb-1">
                Document Requirements
              </p>
              <ul className="text-sm text-yellow-800 space-y-1">
                <li>• Ensure documents are clear, readable, and not expired</li>
                <li>• Accepted formats: JPG, PNG, PDF</li>
                <li>• Maximum file size: 5MB per document</li>
                {accountType === "business" && (
                  <li className="font-semibold">
                    • CAC Certificate is mandatory for business accounts
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>

        {/* Document Upload Cards */}
        <div className="space-y-4">
          {documentTypes.map((docType) => {
            const doc = uploadedDocs[docType.key];
            const isUploaded = doc?.uploaded;

            return (
              <div
                key={docType.key}
                className={`
                  bg-white rounded-xl p-6 border-2 transition-all
                  ${
                    isUploaded
                      ? "border-green-300 bg-green-50"
                      : "border-gray-200 hover:border-green-200"
                  }
                `}
              >
                <div className="flex items-center gap-4">
                  {/* Icon */}
                  <div
                    className={`
                      w-14 h-14 rounded-full flex items-center justify-center flex-shrink-0
                      ${isUploaded ? "bg-green-500" : "bg-gray-200"}
                    `}
                  >
                    {isUploaded ? (
                      <CheckCircle className="w-7 h-7 text-white" />
                    ) : (
                      <Upload className="w-7 h-7 text-gray-500" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-semibold text-gray-900">
                          {docType.title}
                          {docType.required && (
                            <span className="text-red-500 ml-1">*</span>
                          )}
                        </h3>
                        <p className="text-sm text-gray-600 mt-1">
                          {isUploaded ? doc.fileName : docType.description}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2">
                    {isUploaded ? (
                      <>
                        <button
                          onClick={() => handleRemoveDocument(docType.key)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Remove"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleFileUpload(docType.key)}
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium text-sm"
                      >
                        Upload
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Action Buttons */}
        <div className="flex gap-4">
          <button
            onClick={handleBack}
            className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
          >
            <ArrowLeft className="w-5 h-5" />
            Back
          </button>
          <button
            onClick={handleContinue}
            disabled={!hasUploadedDocs}
            className="flex-1 py-3 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-green-200"
          >
            Complete Setup
          </button>
        </div>
      </div>
    </div>
  );
};

export default DocumentUploadScreen;
