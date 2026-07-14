import * as z from "zod";
import {
  AppSwitchEnum,
  ClientTypeEnum,
  CurrencyEnum,
  GenderEnum,
  PartyIdTypeEnum,
  TransferTypeEnum,
} from "../../utils/enums";

export const CreateAccountSchemaVfd = z.object({
  dateOfBirth: z.string(),
  emailAddress: z.string().email(),
  firstname: z.string(),
  lastname: z.string(),
  middlename: z.string().optional(),
  mobileNo: z.string(),
  clientType: z.nativeEnum(ClientTypeEnum),
  gender: z.nativeEnum(GenderEnum),
  bvn: z.string(),
  vfd_account_number: z.string().optional(),
  vfd_account_name: z.string().optional(),
  keycloakId: z.string(),
  switch_name: z.literal(AppSwitchEnum.vfd),
});
export type TCreateAccountSchemaVfd = z.infer<typeof CreateAccountSchemaVfd>;

export const CreateAccountSchemaMojaloop = z.object({
  dateOfBirth: z.string(),
  emailAddress: z.string().email(),
  firstname: z.string(),
  lastname: z.string(),
  middlename: z.string().optional(),
  mobileNo: z.string(),
  clientType: z.nativeEnum(ClientTypeEnum),
  gender: z.nativeEnum(GenderEnum),
  keycloakId: z.string(),
  accountProductIdentifier: z.string().optional(),
  clientTypeId: z.coerce.number().optional(),
  switch_name: z.literal(AppSwitchEnum.mojaloop),
  officeId: z.number().optional(),
});
export type TCreateAccountSchemaMojaloop = z.infer<
  typeof CreateAccountSchemaMojaloop
>;

export const CreateAccountSchema = z.union([
  CreateAccountSchemaMojaloop,
  CreateAccountSchemaVfd,
]);
export type TCreateAccountSchema = z.infer<typeof CreateAccountSchema>;

export const LookupPartySchemaMojaloop = z.object({
  destination: z.string(),
  identifier: z.string().nonempty(),
  identifier_type: z.nativeEnum(PartyIdTypeEnum),
  switch_name: z.literal(AppSwitchEnum.mojaloop),
});
export type TLookupPartySchemaMojaloop = z.infer<
  typeof LookupPartySchemaMojaloop
>;

export const LookupPartySchemaVfd = z.object({
  transfer_type: z.enum(["inter", "intra"]),
  account_number: z.string().nonempty(),
  bank: z.string().nonempty(),
  switch_name: z.literal(AppSwitchEnum.vfd),
});
export type TLookupPartySchemaVfd = z.infer<typeof LookupPartySchemaVfd>;

export const LookupPartySchema = z.union([
  LookupPartySchemaMojaloop,
  LookupPartySchemaVfd,
]);

export const TransferPartySchema = z.object({
  idType: z.nativeEnum(PartyIdTypeEnum),
  idValue: z.string(),
  displayName: z.string().optional(),
  firstName: z.string().optional(),
  middleName: z.string().optional(),
  lastName: z.string().optional(),
  dateOfBirth: z.string().optional(),
  merchantClassificationCode: z.string().optional(),
});

export const InitiateTransferSchemaMojaloop = z.object({
  switch_name: z.literal(AppSwitchEnum.mojaloop),
  amount: z.string(),
  currency: z
    .string()
    .transform((value) => value.toUpperCase())
    .pipe(z.nativeEnum(CurrencyEnum)),
  pin: z.string().min(1).optional(),
  to: TransferPartySchema,
  from: TransferPartySchema,
  geo_code: z
    .object({
      longitude: z.string(),
      latitude: z.string(),
    })
    .optional(),
  note: z.string().min(1).max(256).optional(),
  destination: z.string(),
  tag: z.string().optional(),
  reference: z.string().optional(),
  hold_id: z.string().optional(),
});
export type TInitiateTransferSchemaMojaloop = z.infer<
  typeof InitiateTransferSchemaMojaloop
>;

export const InitiateTransferSchemaVfd = z.object({
  switch_name: z.literal(AppSwitchEnum.vfd),
  fromAccount: z.string().optional(),
  fromAccountId: z.string(),
  fromAccountIdType: z.nativeEnum(PartyIdTypeEnum).optional(),
  currency: z.string().optional(),
  tag: z.string().optional(),
  toAccount: z.object({
    number: z.string(),
    id: z.string(),
    name: z.string(),
    status: z.string(),
  }),
  toBank: z.string(),
  amount: z.string(),
  remark: z.string().nonempty(),
  transferType: z.nativeEnum(TransferTypeEnum).optional(),
  hold_id: z.string().optional(),
});
export type TInitiateTransferSchemaVfd = z.infer<
  typeof InitiateTransferSchemaVfd
>;

export const InitiateTransferSchema = z.discriminatedUnion("switch_name", [
  InitiateTransferSchemaMojaloop,
  InitiateTransferSchemaVfd,
]);

export const CreateSubAccountSchemaMojaloop = z.object({
  dateOfBirth: z.string(),
  emailAddress: z.string().email(),
  firstname: z.string(),
  lastname: z.string(),
  middlename: z.string().optional(),
  mobileNo: z.string(),
  clientType: z.nativeEnum(ClientTypeEnum),
  gender: z.nativeEnum(GenderEnum),
  keycloakId: z.string(),
  accountProductIdentifier: z.string(),
  clientId: z.coerce.number(),
  switch_name: z.literal(AppSwitchEnum.mojaloop),
});
export type TCreateSubAccountSchemaMojaloop = z.infer<
  typeof CreateSubAccountSchemaMojaloop
>;

export const CreateSubAccountSchemaVfd = CreateSubAccountSchemaMojaloop.extend({
  switch_name: z.literal(AppSwitchEnum.vfd),
  previousAccountNo: z.string(),
});
export type TCreateSubAccountSchemaVfd = z.infer<
  typeof CreateSubAccountSchemaVfd
>;

export const CreateSubAccountSchema = z.discriminatedUnion("switch_name", [
  CreateSubAccountSchemaMojaloop,
  CreateSubAccountSchemaVfd,
]);
export type TCreateSubAccountSchema = z.infer<typeof CreateSubAccountSchema>;

export const ReverseTransferSchema = z.object({
  headers: z.object({ tenant: z.string() }),
  body: z.object({
    transaction_id: z.string(),
    reason: z.string().optional(),
  }),
});
