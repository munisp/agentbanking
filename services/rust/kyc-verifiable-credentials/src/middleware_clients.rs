//! Middleware client helpers for Kafka, Dapr, Fluvio, Lakehouse integration

use serde::Serialize;
use std::env;

pub async fn publish_kafka<T: Serialize>(topic: &str, payload: &T) {
    let url = env::var("KAFKA_REST_URL").unwrap_or_else(|_| "http://localhost:8082".into());
    let _ = reqwest::Client::new()
        .post(format!("{}/topics/{}", url, topic))
        .json(payload)
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await;
}

pub async fn publish_fluvio<T: Serialize>(topic: &str, payload: &T) {
    let url = env::var("FLUVIO_URL").unwrap_or_else(|_| "http://localhost:8310".into());
    let _ = reqwest::Client::new()
        .post(format!("{}/produce/{}", url, topic))
        .json(payload)
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await;
}

pub async fn publish_dapr<T: Serialize>(pubsub: &str, topic: &str, payload: &T) {
    let url = env::var("DAPR_URL").unwrap_or_else(|_| "http://localhost:3500".into());
    let _ = reqwest::Client::new()
        .post(format!("{}/v1.0/publish/{}/{}", url, pubsub, topic))
        .json(payload)
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await;
}

pub async fn ingest_lakehouse<T: Serialize>(table: &str, payload: &T) {
    let url = env::var("LAKEHOUSE_URL").unwrap_or_else(|_| "http://localhost:8320".into());
    let body = serde_json::json!({
        "table": table,
        "data": payload,
        "source": "kyc-verifiable-credentials",
    });
    let _ = reqwest::Client::new()
        .post(format!("{}/v1/ingest", url))
        .json(&body)
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await;
}
