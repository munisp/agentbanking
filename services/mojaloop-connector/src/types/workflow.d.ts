import { IAmount, IQuotePayload } from ".";
import { CurrencyEnum, PartyIdTypeEnum } from "../utils/enums";
import * as z from "zod";

export interface WorkflowOptions<T> {
  args: T;
  workflowId: string;
  awaitResult?: boolean;
}

export interface IPutParticipantResponse {
  identifier_type: PartyIdTypeEnum;
  identifier: string;
  fspId: string | null;
}

export interface IRegisterUserToSwitchWorkflowInput {
  fsp_id: string;
  id_type: PartyIdTypeEnum;
  identifier: string;
  currency: string;
}

export interface ILookupFromSwitchWorkflowInput {
  fsp_id: string;
  id_type: PartyIdTypeEnum;
  identifier: string;
  destination?: string;
}

export interface IInitiateTransfer {
  fsp_id: string;
  destination: string;
  payload: IQuotePayload;
  fees: IAmount;
  hold_id?: string;
}

export interface IGetQuoteFromSwitchResponse {
  ilpPacket: string;
  condition: string;
  expiration: string;
  transferAmount: { amount: string; currency: CurrencyEnum };
}

export interface IRegisterUserToSwitchWorkflowInput {
  fsp_id: string;
  id_type: PartyIdTypeEnum;
  identifier: string;
  currency: string;
}

export interface IPutParticipantsResponse {
  fspId: string;
}

export interface IPutPartyResponse {
  party: {
    partyIdInfo: {
      partyIdType: PartyIdTypeEnum; // Example: "MSISDN"
      partyIdentifier: string; // Example: "16135551212"
      partySubIdOrType: string;
      fspId: string;
    };
    merchantClassificationCode: string; // Example: "56"
    name: string;
    personalInfo: {
      complexName: {
        firstName: string;
        middleName?: string;
        lastName: string;
      };
      dateOfBirth: string; // Example: "1966-06-16"
    };
  };
}
