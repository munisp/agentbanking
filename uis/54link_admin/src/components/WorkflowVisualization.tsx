import { useState } from "react";
import { CheckCircle2, Clock, AlertCircle, ArrowRight } from "lucide-react";

// C3: Workflow visualization component for multi-step banking processes

interface WorkflowStep {
  id: string;
  label: string;
  status: "completed" | "active" | "pending" | "failed";
  timestamp?: string;
  actor?: string;
}

interface WorkflowVisualizationProps {
  title: string;
  steps: WorkflowStep[];
  onStepClick?: (stepId: string) => void;
}

const statusIcons = {
  completed: CheckCircle2,
  active: Clock,
  pending: Clock,
  failed: AlertCircle,
};

const statusColors = {
  completed: "text-green-600 bg-green-50 border-green-200",
  active: "text-blue-600 bg-blue-50 border-blue-200 animate-pulse",
  pending: "text-gray-400 bg-gray-50 border-gray-200",
  failed: "text-red-600 bg-red-50 border-red-200",
};

export default function WorkflowVisualization({ title, steps, onStepClick }: WorkflowVisualizationProps) {
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  return (
    <div className="rounded-lg border bg-white p-4 dark:bg-gray-900 dark:border-gray-700">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">{title}</h3>
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {steps.map((step, i) => {
          const Icon = statusIcons[step.status];
          return (
            <div key={step.id} className="flex items-center">
              <button
                onClick={() => {
                  setExpandedStep(expandedStep === step.id ? null : step.id);
                  onStepClick?.(step.id);
                }}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${statusColors[step.status]}`}
                aria-label={`${step.label}: ${step.status}`}
                role="listitem"
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span className="whitespace-nowrap">{step.label}</span>
              </button>
              {i < steps.length - 1 && (
                <ArrowRight className="h-4 w-4 mx-1 text-gray-300 flex-shrink-0" />
              )}
            </div>
          );
        })}
      </div>
      {expandedStep && (
        <div className="mt-3 rounded-md bg-gray-50 dark:bg-gray-800 p-3 text-xs">
          {(() => {
            const step = steps.find(s => s.id === expandedStep);
            if (!step) return null;
            return (
              <div className="space-y-1">
                <div><span className="font-medium">Step:</span> {step.label}</div>
                <div><span className="font-medium">Status:</span> {step.status}</div>
                {step.timestamp && <div><span className="font-medium">Time:</span> {step.timestamp}</div>}
                {step.actor && <div><span className="font-medium">Actor:</span> {step.actor}</div>}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

export const WORKFLOW_TEMPLATES = {
  loanOrigination: [
    { id: "application", label: "Application", status: "completed" as const },
    { id: "kyc", label: "KYC Check", status: "completed" as const },
    { id: "credit", label: "Credit Score", status: "completed" as const },
    { id: "underwriting", label: "Underwriting", status: "active" as const },
    { id: "approval", label: "Approval", status: "pending" as const },
    { id: "disbursement", label: "Disbursement", status: "pending" as const },
  ],
  lcLifecycle: [
    { id: "request", label: "LC Request", status: "completed" as const },
    { id: "review", label: "Bank Review", status: "completed" as const },
    { id: "issue", label: "Issue LC", status: "active" as const },
    { id: "advise", label: "Advise Beneficiary", status: "pending" as const },
    { id: "presentation", label: "Doc Presentation", status: "pending" as const },
    { id: "settlement", label: "Settlement", status: "pending" as const },
  ],
  disputeResolution: [
    { id: "filed", label: "Filed", status: "completed" as const },
    { id: "acknowledged", label: "Acknowledged", status: "completed" as const },
    { id: "investigation", label: "Investigation", status: "active" as const },
    { id: "resolution", label: "Resolution", status: "pending" as const },
    { id: "customer_notification", label: "Notify Customer", status: "pending" as const },
  ],
};
