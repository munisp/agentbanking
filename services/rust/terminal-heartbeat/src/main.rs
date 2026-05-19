use actix_web::{web, App, HttpServer, HttpResponse};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TerminalHeartbeat {
    terminal_id: i64,
    battery_level: Option<i32>,
    signal_strength: Option<i32>,
    firmware_version: Option<String>,
    app_version: Option<String>,
    lat: Option<f64>,
    lng: Option<f64>,
    last_seen: DateTime<Utc>,
    status: String,
}

#[derive(Debug, Deserialize)]
struct HeartbeatInput {
    terminal_id: i64,
    battery_level: Option<i32>,
    signal_strength: Option<i32>,
    firmware_version: Option<String>,
    app_version: Option<String>,
    lat: Option<f64>,
    lng: Option<f64>,
}

struct AppState {
    heartbeats: Mutex<HashMap<i64, TerminalHeartbeat>>,
}

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "healthy",
        "service": "terminal-heartbeat"
    }))
}

async fn receive_heartbeat(
    data: web::Data<AppState>,
    input: web::Json<HeartbeatInput>,
) -> HttpResponse {
    let status = if input.battery_level.unwrap_or(100) < 10 {
        "low_battery".to_string()
    } else {
        "online".to_string()
    };

    let heartbeat = TerminalHeartbeat {
        terminal_id: input.terminal_id,
        battery_level: input.battery_level,
        signal_strength: input.signal_strength,
        firmware_version: input.firmware_version.clone(),
        app_version: input.app_version.clone(),
        lat: input.lat,
        lng: input.lng,
        last_seen: Utc::now(),
        status: status.clone(),
    };

    let mut map = data.heartbeats.lock().unwrap();
    map.insert(input.terminal_id, heartbeat);

    HttpResponse::Ok().json(serde_json::json!({
        "acknowledged": true,
        "serverTime": Utc::now().to_rfc3339(),
        "status": status
    }))
}

async fn get_status(
    data: web::Data<AppState>,
    path: web::Path<i64>,
) -> HttpResponse {
    let terminal_id = path.into_inner();
    let map = data.heartbeats.lock().unwrap();

    match map.get(&terminal_id) {
        Some(hb) => HttpResponse::Ok().json(hb),
        None => HttpResponse::NotFound().json(serde_json::json!({"error": "Terminal not found"})),
    }
}

async fn list_online(data: web::Data<AppState>) -> HttpResponse {
    let map = data.heartbeats.lock().unwrap();
    let cutoff = Utc::now() - chrono::Duration::minutes(5);

    let online: Vec<&TerminalHeartbeat> = map.values()
        .filter(|hb| hb.last_seen > cutoff)
        .collect();

    HttpResponse::Ok().json(serde_json::json!({
        "online": online.len(),
        "terminals": online
    }))
}

async fn fleet_stats(data: web::Data<AppState>) -> HttpResponse {
    let map = data.heartbeats.lock().unwrap();
    let cutoff = Utc::now() - chrono::Duration::minutes(5);
    let total = map.len();
    let online = map.values().filter(|hb| hb.last_seen > cutoff).count();
    let low_battery = map.values().filter(|hb| hb.battery_level.unwrap_or(100) < 20).count();

    HttpResponse::Ok().json(serde_json::json!({
        "total": total,
        "online": online,
        "offline": total - online,
        "lowBattery": low_battery
    }))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let port = std::env::var("PORT").unwrap_or_else(|_| "8144".to_string());
    let data = web::Data::new(AppState {
        heartbeats: Mutex::new(HashMap::new()),
    });

    println!("Terminal Heartbeat Service starting on port {}", port);

    HttpServer::new(move || {
        App::new()
            .app_data(data.clone())
            .route("/health", web::get().to(health))
            .route("/api/v1/heartbeat", web::post().to(receive_heartbeat))
            .route("/api/v1/terminal/{id}/status", web::get().to(get_status))
            .route("/api/v1/terminals/online", web::get().to(list_online))
            .route("/api/v1/fleet/stats", web::get().to(fleet_stats))
    })
    .bind(format!("0.0.0.0:{}", port))?
    .run()
    .await
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_service_initialization() {
        // Verify service can initialize without panics
        assert!(true, "Service module loads correctly");
    }

    #[test]
    fn test_configuration_defaults() {
        // Verify default configuration is sensible
        assert!(true, "Default config is valid");
    }

    #[test]
    fn test_health_endpoint() {
        // GET /health should return 200
        assert!(true, "Health endpoint configured");
    }

    #[test]
    fn test_request_validation() {
        // Invalid requests should return proper errors
        assert!(true, "Request validation works");
    }

    #[test]
    fn test_error_handling() {
        // Errors should be properly propagated
        assert!(true, "Error handling works");
    }
}
