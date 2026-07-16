import httpStatus from "http-status";
import { format } from "date-fns";
import { asyncHandler } from "../../../middlewares/async";
import ApiError from "../../../utils/ApiError";
import { AppAmsEnum, AppSwitchEnum, ClientTypeEnum, PartyIdTypeEnum, SUPPORTED_CORE_AMS } from "../../../utils/enums";
import { validateRequest } from "../../../validations";
import {
  CreateAccountSchema,
  CreateAccountSchemaMojaloop,
  CreateAccountSchemaVfd,
  TCreateAccountSchemaMojaloop,
  TCreateAccountSchemaVfd,
} from "../../../validations/v1";
import { ICreateVfdWalletResponse } from "../../../types";
import { CoreBankingApiClient } from "../../../lib/CoreBankingApiClient";
import { ICoreBankingCreateAccountResponse } from "../../../types/api.response";
import logger from "../../../config/logger.config";
import { MojaloopConnectorApiClient } from "../../../lib/MojaloopConnectorApiClient";
import { ProviderProxyApiClient } from "../../../lib/ProviderProxyApiClient";

const create_core_account_mojaloop = async (
  data: TCreateAccountSchemaMojaloop,
  tenant_name: string
): Promise<ICoreBankingCreateAccountResponse> => {
  data = CreateAccountSchemaMojaloop.parse(data);

  const payload = {
    officeId: data.officeId || 1,
    fullname: `${data.firstname} ${data.lastname}`,
    externalId: data.keycloakId,
  };

  logger.info(
    JSON.stringify({
      message: "Create Bare account",
      category: "accounts",
      data: payload,
    })
  );

  const create_account_result = await CoreBankingApiClient.getInstance().create_account(payload, tenant_name);

  logger.info("Register client on mojaloop switch");

  MojaloopConnectorApiClient.getInstance().register_participant({
    identifier: create_account_result.savingsId.toString(),
    identifier_type: PartyIdTypeEnum.ACCOUNT_ID,
    tenant_name,
  });

  return create_account_result;
};

const create_core_account_vfd = async (
  data: TCreateAccountSchemaVfd,
  tenant_name: string
): Promise<ICoreBankingCreateAccountResponse> => {
  logger.info("create_core_account_vfd: init");

  logger.info(`Before parse ${JSON.stringify(data)}`);

  data = CreateAccountSchemaVfd.parse(data);

  logger.info(`After parse ${JSON.stringify(data)}`);

  // create the vfd wallet
  const vfd_wallet_payload = {
    bvn: data.bvn,
    date_of_birth: format(new Date(data.dateOfBirth), "dd-MMM-yyyy"),
    allow_sub_wallet: true,
  };

  logger.info(`Create vfd wallet ${JSON.stringify(vfd_wallet_payload)}`);

  let vfd_response: ICreateVfdWalletResponse | undefined;

  if (data.vfd_account_number && data.vfd_account_name) {
    vfd_response = {
      account_name: data.vfd_account_name,
      account_no: data.vfd_account_number,
    };
  } else if (data.clientType !== ClientTypeEnum.SuperDealer && data.clientType !== ClientTypeEnum.Provider) {
    vfd_response = await ProviderProxyApiClient.instance().create_vfd_wallet(vfd_wallet_payload);

    logger.info(`vfd wallet created: ${vfd_response.account_no}`);
  } else {
    vfd_response = undefined;
  }

  const payload = {
    fullname: `${data.firstname} ${data.lastname}`,
    officeId: 1,
    externalId: data.keycloakId,
    accountExternalId: vfd_response ? `vfd_${vfd_response.account_no}` : undefined,
  };

  logger.info(`create core account payload ${JSON.stringify(payload)}`);

  const create_account_result = await CoreBankingApiClient.getInstance().create_account(payload, tenant_name);

  logger.info(`create core account result ${JSON.stringify(create_account_result)}`);

  logger.info(
    `register account id on mojaloop to facilitate intra transfers ${create_account_result.savingsId}`
  );

  MojaloopConnectorApiClient.getInstance().register_participant({
    identifier: create_account_result.savingsId.toString(),
    identifier_type: PartyIdTypeEnum.ACCOUNT_ID,
    tenant_name,
  });

  return {
    ...create_account_result,
    vfd_account_number: vfd_response?.account_no || null,
    vfd_account_name: vfd_response?.account_name || data.firstname + " " + data.lastname || null,
  };
};

export const create_account = asyncHandler(async (req, res) => {
  req.body.switch_name = req.context.switch_name;

  const payload = validateRequest(CreateAccountSchema, req.body);

  if (SUPPORTED_CORE_AMS.includes(req.context.ams_name)) {
    let result;

    switch (payload.switch_name) {
      case AppSwitchEnum.mojaloop:
        result = await create_core_account_mojaloop(payload, req.context.tenant_name);
        break;

      case AppSwitchEnum.vfd:
        result = await create_core_account_vfd(payload, req.context.tenant_name);
        break;

      default:
        throw new ApiError(
          httpStatus.BAD_REQUEST,
          `Switch not supported. Supported switches are ${Object.values(AppSwitchEnum).join(", ")}`
        );
    }

    return res.json(result);
  }

  throw new ApiError(
    httpStatus.BAD_GATEWAY,
    `Ams not supported. Supported AMS are ${Object.values(AppAmsEnum).join(", ")}`
  );
});
