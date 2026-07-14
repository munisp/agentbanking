import { IVerifyDataResult, IVerifyFaceResult } from "./verification";

export type UnwrapPromise<T> = T extends Promise<infer U> ? U : T;

export interface WorkflowOptions<T> {
  args: T;
  workflowId: string;
  defaultErrorMessage?: string;
  isDaemon?: boolean;
}

export interface BallerineWorkflow {
  workflowDefinitionId: string;
  workflowRuntimeId: string;
  ballerineEntityId: string;
}

export interface KycWorkflowArgs {
  id: string;
  firstName: string;
  lastName: string;
  phone: string;
  UIN: string;
  dateOfBirth?: string;
  callBackUrl?: string;
  metadata?: any;
}

export interface KycWorkflowResult {
  id: string;
  faceVerificationResult: IVerifyFaceResult;
  dataVerificationResult: IVerifyDataResult;
  documentVerificationResult?: any;
  score?: number;
  metadata?: any;
}
