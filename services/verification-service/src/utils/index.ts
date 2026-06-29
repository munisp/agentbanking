export function getWorkflowErrorMessage(error: any, defaultErrorMessage: string) {
  while (error?.cause) {
    error = error.cause;
  }
  return error?.message || defaultErrorMessage;
}
