import httpStatus from "http-status";
import { asyncHandler } from "../../../middlewares/async";
import ApiError from "../../../utils/ApiError";
import { validateRequest } from "../../../validations";
import {
  CreateSubAccountSchema,
  CreateSubAccountSchemaMojaloop,
  CreateSubAccountSchemaVfd,
  TCreateSubAccountSchemaMojaloop,
} from "../../../validations/v1";
import { AppAmsEnum, AppSwitchEnum, PartyIdTypeEnum, SUPPORTED_CORE_AMS } from "../../../utils/enums";
import { CoreBankingApiClient } from "../../../lib/CoreBankingApiClient";
import { ICoreBankingCreateSubAccountResponse } from "../../../types/api.response";
import logger from "../../../config/logger.config";
import { MojaloopConnectorApiClient } from "../../../lib/MojaloopConnectorApiClient";
import { ProviderProxyApiClient } from "../../../lib/ProviderProxyApiClient";

const create_core_sub_account_mojaloop = async (
  data: TCreateSubAccountSchemaMojaloop,
  tenant_name: string
): Promise<ICoreBankingCreateSubAccountResponse> => {
  data = CreateSubAccountSchemaMojaloop.parse(data);

  const create_account_result = await CoreBankingApiClient.getInstance().create_sub_account(
    {
      fullname: `${data.firstname} ${data.lastname}`,
      keycloakId: data.keycloakId,
    },
    tenant_name
  );

  logger.info("Register client on mojaloop switch");

  MojaloopConnectorApiClient.getInstance().register_participant({
    identifier: data.mobileNo,
    tenant_name,
  });

  return create_account_result;
};

const create_core_sub_account_vfd = async (data: unknown, tenant_name: string) => {
  const validated_data = CreateSubAccountSchemaVfd.parse(data);

  // Create VFD Account
  const vfd_wallet_payload = {
    prev_account_no: validated_data.previousAccountNo,
  };

  const vfd_response = await ProviderProxyApiClient.instance().create_vfd_sub_wallet(vfd_wallet_payload);

  const create_account_result = await CoreBankingApiClient.getInstance().create_sub_account(
    {
      fullname: `${validated_data.firstname} ${validated_data.lastname}`,
      keycloakId: validated_data.keycloakId,
      accountExternalId: vfd_response ? `vfd_${vfd_response.account_no}` : undefined,
    },
    tenant_name
  );

  logger.info("Register client on mojaloop switch");

  MojaloopConnectorApiClient.getInstance().register_participant({
    identifier: create_account_result.savingsId.toString(),
    identifier_type: PartyIdTypeEnum.ACCOUNT_ID,
    tenant_name,
  });

  return {
    ...create_account_result,
    vfd_account_number: vfd_response.account_no,
    vfd_account_name: vfd_response.account_name,
  };
};

export const create_sub_account = asyncHandler(async (req, res) => {
  req.body.switch_name = req.context.switch_name;

  const payload = validateRequest(CreateSubAccountSchema, req.body);

  if (SUPPORTED_CORE_AMS.includes(req.context.ams_name)) {
    let result;

    switch (payload.switch_name) {
      case AppSwitchEnum.mojaloop:
        result = await create_core_sub_account_mojaloop(payload, req.context.tenant_name);
        break;

      case AppSwitchEnum.vfd:
        result = await create_core_sub_account_vfd(payload, req.context.tenant_name);
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
