import { MojaloopApiClient } from "../lib/MojaloopApiClient";
import { PartyIdTypeEnum } from "../utils/enums";

export const lookup_party = async (
  fsp_id: string,
  id_type: PartyIdTypeEnum,
  identifier: string,
  destination?: string
) => {
  await MojaloopApiClient.getInstance().lookup_party(fsp_id, id_type, identifier, destination);
};
