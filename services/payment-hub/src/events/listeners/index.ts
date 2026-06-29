import { DaprServerService } from "../../services";
import { EXTERNAL_DAPR_EVENT_PUBSUB_NAME } from "../../utils/constants";
import { PubSubTopics } from "../../utils/enums";
import { handlers } from "../handlers";

export function subscribeToPubsubTopics(server: DaprServerService) {
  server.subscribe(PubSubTopics.quote_agreed, handlers.quote_agreed);
  server.subscribe(PubSubTopics.quote_failed, handlers.quote_failed);
  server.subscribe(PubSubTopics.quote_initiated, handlers.quote_initiated);
  server.subscribe(PubSubTopics.transaction_failed, handlers.txn_failed);
  server.subscribe(PubSubTopics.reserve_transaction, handlers.reserve_txn);
  server.subscribe(PubSubTopics.transaction_completed, handlers.complete_txn);
  server.subscribe(
    PubSubTopics.update_local_transaction_id,
    handlers.update_local_txn_id,
  );
  server.subscribe(
    PubSubTopics.initiate_txn_generic,
    handlers.initiate_txn_generic,
  );
  server.subscribe(PubSubTopics.reverse_transfer, handlers.reverse_txn);
  server.subscribe(
    PubSubTopics.VFD_INFLOW_WEBHOOK,
    handlers.process_vfd_inflow,
    EXTERNAL_DAPR_EVENT_PUBSUB_NAME,
  );
  server.subscribe(
    PubSubTopics.INFLOW_WEBHOOK,
    handlers.process_inflow,
    EXTERNAL_DAPR_EVENT_PUBSUB_NAME,
  );
}
