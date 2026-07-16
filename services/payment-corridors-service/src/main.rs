mod config;
mod error;
mod rails;
mod router;
mod service;

use std::net::SocketAddr;

use metrics_exporter_prometheus::PrometheusBuilder;
use tonic::transport::Server;
use tracing::info;
use tracing_subscriber::{fmt, EnvFilter};

use crate::{
    config::Settings,
    router::RailSelector,
    service::{
        api_key_interceptor,
        proto::corridor_service_server::CorridorServiceServer,
        CorridorHandler,
    },
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Structured JSON logging — filter via RUST_LOG env var
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env()
            .add_directive("payment_corridor=info".parse()?))
        .json()
        .init();

    let settings = Settings::load().map_err(|e| {
        eprintln!("Failed to load configuration: {}", e);
        e
    })?;

    // Prometheus metrics endpoint
    if settings.metrics.enabled {
        let metrics_addr: SocketAddr =
            format!("0.0.0.0:{}", settings.metrics.port).parse()?;
        PrometheusBuilder::new()
            .with_http_listener(metrics_addr)
            .install()?;
        info!(addr = %metrics_addr, "metrics endpoint started");
    }

    let addr: SocketAddr =
        format!("{}:{}", settings.server.host, settings.server.port).parse()?;

    let selector = RailSelector::new(settings.clone());
    let handler  = CorridorHandler::new(selector);
    let svc      = CorridorServiceServer::with_interceptor(
        handler,
        api_key_interceptor(settings.security.clone()),
    );

    info!(
        addr = %addr,
        enforce_api_key = settings.security.enforce_api_key,
        "payment-corridor gRPC server starting"
    );

    Server::builder()
        .add_service(svc)
        .serve(addr)
        .await?;

    Ok(())
}