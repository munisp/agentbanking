export interface InitVerification {
  clientId: string;
  state: string;
  callbackUrl: string;
  redirectUrl: string;
  userId: string;
}

export interface IVerifyFace {
  nin: string;
  base64Image: string;
  webhook?: {
    callbackUrl: string;
    userId: string;
    clientid: string;
    state: string;
  };
}

export interface IVerifyFaceResult {
  success: boolean;
  similarity: number;
  ninData: {
    nin: string;
    firstName: string;
    lastName: string;
    dateOfBirth: string;
    phone: string;
  };
}

export interface IVerifyDataResult {
  firstName: boolean;
  lastName: boolean;
  dateOfBirth: boolean;
  phone: boolean;
  UIN: boolean;
}
