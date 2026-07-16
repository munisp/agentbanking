import { MojaloopApiClient } from "../lib/MojaloopApiClient";
import { PartyIdTypeEnum } from "../utils/enums";

export const register_participant = async (
  fsp_id: string,
  id_type: PartyIdTypeEnum,
  identifier: string,
  currency: string
) => {
  await MojaloopApiClient.getInstance().register_participant(fsp_id, id_type, identifier, currency);
};
