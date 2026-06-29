import httpStatus from "http-status";
import logger from "../../../config/logger.config";
import { MojaloopConnectorApiClient } from "../../../lib/MojaloopConnectorApiClient";
import { VfdConnectorApiClient } from "../../../lib/VfdConnectorApiClient";
import { asyncHandler } from "../../../middlewares/async";
import ApiError from "../../../utils/ApiError";
import {
  AppAmsEnum,
  AppSwitchEnum,
  SUPPORTED_CORE_AMS,
  TransferTypeEnum,
} from "../../../utils/enums";
import { validateRequest } from "../../../validations";
import {
  InitiateTransferSchema,
  InitiateTransferSchemaMojaloop,
  InitiateTransferSchemaVfd,
  TInitiateTransferSchemaMojaloop,
  TInitiateTransferSchemaVfd,
} from "../../../validations/v1";

const getHeaderValue = (
  headers: Record<string, string | string[] | undefined>,
  name: string,
) => {
  const value = headers[name.toLowerCase()];
  return Array.isArray(value) ? value[0] : value;
};

export const initiate_transfer_mojaloop = async (
  data: TInitiateTransferSchemaMojaloop,
  headers: Record<string, string> = {},
) => {
  data = InitiateTransferSchemaMojaloop.parse(data);
  return await MojaloopConnectorApiClient.getInstance().initialize_transfer(
    data,
    headers,
  );
};

export const initiate_transfer_vfd = async (
  data: TInitiateTransferSchemaVfd,
  tenant: string,
) => {
  data = InitiateTransferSchemaVfd.parse(data);

  if (data.toBank == "999999") {
    data.transferType = TransferTypeEnum.INTRA;
  }

  return await VfdConnectorApiClient.instance().initialize_transfer(
    data,
    tenant,
  );
};

export const initiate_transfer = asyncHandler(async (req, res) => {
  logger.info(
    `Initiate transfer request path=${req.originalUrl} tenant=${req.context?.tenant_name || "unknown"} switch=${req.context?.switch_name || "unknown"} ams=${req.context?.ams_name || "unknown"}`,
  );

  logger.info(`headers: ${JSON.stringify(req.headers)}`);

  req.body.switch_name = req.context.switch_name;

  const tenantId =
    getHeaderValue(req.headers, "x-tenant-id") ||
    getHeaderValue(req.headers, "x-tenent-id") ||
    req.context.tenant_name;

  const keycloakId =
    getHeaderValue(req.headers, "x-keycloak-id") || req.context.tenant_name;

  const ledgerId =
    getHeaderValue(req.headers, "x-ledger-id") || req.context.tenant_name;

  const mintAccountId =
    getHeaderValue(req.headers, "x-mint-account-id") || req.context.tenant_name;

  const pin =
    req.body.pin ||
    getHeaderValue(req.headers, "x-payer-pin") ||
    getHeaderValue(req.headers, "x-pin");

  req.body.pin = pin;

  const forwardedHeaders = {
    "x-tenant-id": tenantId,
    "x-keycloak-id": keycloakId,
    "x-ledger-id": ledgerId,
    "x-mint-account-id": mintAccountId,
  };

  const payload = validateRequest(InitiateTransferSchema, req.body);

  if (SUPPORTED_CORE_AMS.includes(req.context.ams_name)) {
    let result;

    switch (payload.switch_name) {
      case AppSwitchEnum.mojaloop:
        {
          const mojaloopPayload = InitiateTransferSchemaMojaloop.parse(payload);
        logger.info(
          `Processing mojaloop transfer from=${mojaloopPayload.from.idValue} to=${mojaloopPayload.to.idValue} amount=${mojaloopPayload.amount} currency=${mojaloopPayload.currency}`,
        );
        logger.info(`Forwarded headers: ${JSON.stringify(forwardedHeaders)}`);
        result = await initiate_transfer_mojaloop(
          mojaloopPayload,
          forwardedHeaders,
        );
        break;
        }

      case AppSwitchEnum.vfd:
        {
          const vfdPayload = InitiateTransferSchemaVfd.parse(payload);
        logger.info(
          `Processing vfd transfer fromAccountId=${vfdPayload.fromAccountId} toAccount=${vfdPayload.toAccount.number} amount=${vfdPayload.amount}`,
        );
        result = await initiate_transfer_vfd(
          vfdPayload,
          req.context.tenant_name,
        );
        break;
        }

      default:
        throw new ApiError(httpStatus.BAD_GATEWAY, "Switch not supported.");
    }

    logger.info(
      `Initiate transfer success path=${req.originalUrl} tenant=${req.context.tenant_name} switch=${payload.switch_name}`,
    );

    return res.json(result);
  }

  throw new ApiError(httpStatus.BAD_GATEWAY, `Ams not supported.`);
});
