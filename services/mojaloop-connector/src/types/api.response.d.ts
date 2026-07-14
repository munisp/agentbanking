export interface IPaginatedResponse<T extends object> {
  data: T[];
  total: number;
}

export interface IFineractWithdrawResponse {
  success: boolean;
  message: string;
  transactionId: string;
  resourceId?: number;
}
