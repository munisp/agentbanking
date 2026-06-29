# MQTT Bridge — POS Terminal Integration

Lightweight pub/sub layer for POS terminals and mobile agents operating in low-bandwidth or
intermittent connectivity environments.

## Topic convention

```
pos/{terminal_id}/transactions     # POS → platform: transaction payloads
pos/{terminal_id}/status           # POS → platform: heartbeat / connection state
agent/{agent_id}/commands          # platform → agent: float top-up alerts, config pushes
agent/{agent_id}/notifications     # platform → agent: push notifications
platform/broadcasts                # platform → all: rate changes, downtime notices
```

## Bridge architecture

```
POS Terminal (MQTT client)
        │
        ▼  MQTT (port 1883 / WSS 9001)
   Mosquitto broker
        │
        ▼  mqtt-bridge microservice (subscribes to all topics)
   Kafka topic: mqtt.inbound
        │
        ▼  Consumers in relevant microservices
```

The `mqtt-bridge` service (to be implemented as an extension of `realtime-notification-service`)
subscribes to all `pos/+/transactions` and `agent/+/commands` topics, validates, and re-publishes
to the appropriate Kafka topics for processing by downstream services.

## Production

Replace Mosquitto with EMQX for:
- Horizontal scaling (cluster mode)
- Rule engine (transform/filter before Kafka bridge)
- Built-in ACL and JWT authentication
- Dashboard UI at `:18083`
