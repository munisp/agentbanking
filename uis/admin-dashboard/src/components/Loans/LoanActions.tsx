import { ArrowDownCircle, CheckCircle, XCircle } from "lucide-react";
import React from "react";

interface LoanActionsProps {
  status: string;
  onApprove: () => void;
  onReject: () => void;
  onDisburse?: () => void;
  disabled?: boolean;
}

const LoanActions: React.FC<LoanActionsProps> = ({
  status,
  onApprove,
  onReject,
  onDisburse,
  disabled,
}) => {
  if (status.toLowerCase() === "pending") {
    return (
      <div className="flex gap-2">
        <button
          className="inline-flex items-center px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
          onClick={onApprove}
          disabled={disabled}
        >
          <CheckCircle className="h-4 w-4 mr-1" /> Approve
        </button>
        <button
          className="inline-flex items-center px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
          onClick={onReject}
          disabled={disabled}
        >
          <XCircle className="h-4 w-4 mr-1" /> Reject
        </button>
      </div>
    );
  }
  if (status.toLowerCase() === "approved" && onDisburse) {
    return (
      <div className="flex gap-2">
        <button
          className="inline-flex items-center px-3 py-1 bg-[var(--tenant-primary-color,#002082)] text-white rounded hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50"
          onClick={onDisburse}
          disabled={disabled}
        >
          <ArrowDownCircle className="h-4 w-4 mr-1" /> Disburse
        </button>
      </div>
    );
  }
  return null;
};

export default LoanActions;
