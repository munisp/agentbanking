import { complete_txn } from "./complete_txn";
import { initiate_txn_generic } from "./initiate_txn_generic";
import { process_inflow } from "./process_inflow";
import { process_vfd_inflow } from "./process_vfd_inflow";
import { quote_agreed } from "./quote_agreed";
import { quote_failed } from "./quote_failed";
import { quote_initiated } from "./quote_initiated";
import { reserve_txn } from "./reserve_txn";
import { reverse_txn } from "./reverse_txn";
import { txn_failed } from "./txn_failed";
import { update_local_txn_id } from "./update_local_txn_id";

export const handlers = {
  quote_initiated,
  quote_agreed,
  quote_failed,
  txn_failed,
  reserve_txn,
  complete_txn,
  update_local_txn_id,
  initiate_txn_generic,
  process_vfd_inflow,
  process_inflow,
  reverse_txn,
};
