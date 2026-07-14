import logger from "../../../config/logger.config";
import { MojaloopConnectorApiClient } from "../../../lib/MojaloopConnectorApiClient";
import { VfdConnectorApiClient } from "../../../lib/VfdConnectorApiClient";
import { asyncHandler } from "../../../middlewares/async";
import { AppSwitchEnum, TransferTypeEnum } from "../../../utils/enums";
import { validateRequest } from "../../../validations";
import {
  LookupPartySchema,
  LookupPartySchemaMojaloop,
  LookupPartySchemaVfd,
  TLookupPartySchemaMojaloop,
  TLookupPartySchemaVfd,
} from "../../../validations/v1";

const lookup_party_mojaloop = async (
  data: TLookupPartySchemaMojaloop,
  tenant_name: string
) => {
  data = LookupPartySchemaMojaloop.parse(data);
  logger.info(`lookup_party_mojaloop ${JSON.stringify(data)}`);
  return await MojaloopConnectorApiClient.getInstance().lookup_party(
    data,
    tenant_name
  );
};

const lookup_party_vfd = async (data: TLookupPartySchemaVfd) => {
  data = LookupPartySchemaVfd.parse(data);

  if (data.bank == "999999") {
    data.transfer_type = TransferTypeEnum.INTRA;
  }

  logger.info(`lookup_party_vfd ${JSON.stringify(data)}`);

  return await VfdConnectorApiClient.instance().lookup_party(data);
};

export const lookup_party = asyncHandler(async (req, res) => {
  req.body.switch_name = req.context.switch_name;

  const payload = validateRequest(LookupPartySchema, req.body);

  logger.info(`lookup_party ${JSON.stringify(payload)}`);

  let result;

  switch (payload.switch_name) {
    case AppSwitchEnum.mojaloop:
      result = await lookup_party_mojaloop(payload, req.context.tenant_name);
      break;

    case AppSwitchEnum.vfd:
      result = await lookup_party_vfd(payload);
      break;
  }

  logger.info(`result: ${JSON.stringify(result)} ${typeof result}`);

  res.json({ result });
});
