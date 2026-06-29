import { MojaloopApiClient } from "../lib/MojaloopApiClient";
import { PartyIdTypeEnum } from "../utils/enums";

export const lookup_participants = async (fsp_id: string, id_type: PartyIdTypeEnum, identifier: string) => {
  await MojaloopApiClient.getInstance().lookup_participants(fsp_id, id_type, identifier);
};
