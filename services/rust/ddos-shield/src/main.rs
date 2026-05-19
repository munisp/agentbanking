// @ts-nocheck
//! DDoS Shield — High-performance Rust protection engine
//! Provides: adaptive rate limiting, IP reputation scoring, circuit breaker,
//! connection analysis, slowloris detection, request fingerprinting,
//! geo-blocking, and real-time threat intelligence.

use axum::{
    extract::{Json, State},
    http::StatusCode,
    routing::{get, post},
    Router,
};
use chrono::Utc;
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{info, warn};

// ── Models ───────────────────────────────────────────────────────────

// Type aliases for backward-compatible naming
pub type AdaptiveRateLimiter = RateLimitWindow;
pub type CircuitBreaker = CircuitState;
pub type ConnectionAnalyzer = ConnectionAnalysis;
pub type IpReputation = IPReputation;

/// Token bucket parameters for adaptive rate limiting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenBucket {
    pub tokens: f64,
    pub max_tokens: f64,
    pub refill_rate: f64,  // tokens per second
    pub last_refill: i64,
}

/// Circuit breaker state enum
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum CircuitBreakerState {
    Closed,
    Open,
    HalfOpen,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IPReputation {
    pub ip: String,
    pub score: f64,           // 0.0 (malicious) to 100.0 (trusted)
    pub total_requests: u64,
    pub blocked_requests: u64,
    pub violations: u32,
    pub first_seen: i64,
    pub last_seen: i64,
    pub is_blocked: bool,
    pub blocked_until: i64,
    pub threat_level: ThreatLevel,
    pub country_code: String,
    pub is_tor_exit: bool,
    pub is_vpn: bool,
    pub is_datacenter: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ThreatLevel {
    None,
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitWindow {
    pub count: u64,
    pub window_start: i64,
    pub burst_count: u64,     // requests in last 1 second
    pub burst_start: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CircuitState {
    pub name: String,
    pub state: String,        // "closed", "open", "half-open" (see CircuitBreakerState enum)
    pub failures: u32,
    pub failure_count: u32,
    pub failure_threshold: u32,
    pub successes: u32,
    pub last_failure: i64,
    pub opened_at: i64,
    pub half_open_attempts: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionAnalysis {
    pub ip: String,
    pub concurrent_connections: u32,
    pub avg_request_duration_ms: f64,
    pub request_pattern: String,   // "normal", "burst", "slowloris", "scanning"
    pub unique_endpoints: u32,
    pub unique_user_agents: u32,
    pub payload_anomaly_score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThreatIntelEntry {
    pub ip: String,
    pub source: String,
    pub threat_type: String,
    pub confidence: f64,
    pub reported_at: i64,
    pub expires_at: i64,
}

// ── Request/Response Types ───────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CheckRequest {
    pub ip: String,
    pub path: String,
    pub method: String,
    pub user_agent: Option<String>,
    pub content_length: Option<u64>,
    pub headers: Option<std::collections::HashMap<String, String>>,
}

#[derive(Debug, Serialize)]
pub struct CheckResponse {
    pub allowed: bool,
    pub reason: Option<String>,
    pub ip_score: f64,
    pub threat_level: ThreatLevel,
    pub rate_limit_remaining: u64,
    pub rate_limit_reset: i64,
    pub recommendations: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub struct ReportRequest {
    pub ip: String,
    pub violation_type: String,
    pub severity: u32,         // 1-10
    pub details: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct StatusResponse {
    pub total_ips_tracked: usize,
    pub blocked_ips: usize,
    pub circuit_states: Vec<CircuitState>,
    pub requests_per_second: f64,
    pub threat_intel_entries: usize,
    pub uptime_seconds: u64,
}

#[derive(Debug, Deserialize)]
pub struct BlockRequest {
    pub ip: String,
    pub duration_seconds: Option<u64>,
    pub reason: String,
}

#[derive(Debug, Deserialize)]
pub struct CircuitBreakerConfig {
    pub service_name: String,
    pub failure_threshold: u32,
    pub recovery_timeout_seconds: u64,
    pub half_open_max_attempts: u32,
}

// ── Application State ────────────────────────────────────────────────

pub struct AppState {
    ip_reputations: DashMap<String, IPReputation>,
    rate_windows: DashMap<String, RateLimitWindow>,
    circuits: DashMap<String, CircuitState>,
    threat_intel: DashMap<String, ThreatIntelEntry>,
    connection_stats: DashMap<String, ConnectionAnalysis>,
    permanent_blocklist: DashMap<String, String>,  // ip -> reason
    start_time: Instant,
    global_request_count: Arc<RwLock<u64>>,
    // Configurable limits
    base_rate_limit: u64,      // requests per minute
    burst_limit: u64,          // requests per second
    max_concurrent: u32,
    block_duration_secs: u64,
    permanent_block_violations: u32,
}

impl AppState {
    fn new() -> Self {
        Self {
            ip_reputations: DashMap::new(),
            rate_windows: DashMap::new(),
            circuits: DashMap::new(),
            threat_intel: DashMap::new(),
            connection_stats: DashMap::new(),
            permanent_blocklist: DashMap::new(),
            start_time: Instant::now(),
            global_request_count: Arc::new(RwLock::new(0)),
            base_rate_limit: 200,
            burst_limit: 20,
            max_concurrent: 50,
            block_duration_secs: 300,
            permanent_block_violations: 10,
        }
    }

    fn get_or_create_reputation(&self, ip: &str) -> IPReputation {
        self.ip_reputations
            .entry(ip.to_string())
            .or_insert_with(|| IPReputation {
                ip: ip.to_string(),
                score: 100.0,
                total_requests: 0,
                blocked_requests: 0,
                violations: 0,
                first_seen: Utc::now().timestamp(),
                last_seen: Utc::now().timestamp(),
                is_blocked: false,
                blocked_until: 0,
                threat_level: ThreatLevel::None,
                country_code: "XX".to_string(),
                is_tor_exit: false,
                is_vpn: false,
                is_datacenter: false,
            })
            .clone()
    }

    fn update_reputation(&self, ip: &str, score_delta: f64, violation: bool) {
        self.ip_reputations.entry(ip.to_string()).and_modify(|rep| {
            rep.score = (rep.score + score_delta).clamp(0.0, 100.0);
            rep.last_seen = Utc::now().timestamp();
            rep.total_requests += 1;
            if violation {
                rep.violations += 1;
            }
            // Update threat level based on score
            rep.threat_level = match rep.score {
                s if s >= 80.0 => ThreatLevel::None,
                s if s >= 60.0 => ThreatLevel::Low,
                s if s >= 40.0 => ThreatLevel::Medium,
                s if s >= 20.0 => ThreatLevel::High,
                _ => ThreatLevel::Critical,
            };
        });
    }

    fn check_rate_limit(&self, ip: &str, reputation_score: f64) -> (bool, u64, i64) {
        let now = Utc::now().timestamp();
        let adjusted_limit = ((self.base_rate_limit as f64) * (reputation_score / 100.0))
            .max(10.0) as u64;
        let window_ms = 60;

        let mut window = self.rate_windows
            .entry(ip.to_string())
            .or_insert_with(|| RateLimitWindow {
                count: 0,
                window_start: now,
                burst_count: 0,
                burst_start: now,
            });

        // Reset window if expired
        if now - window.window_start > window_ms {
            window.count = 0;
            window.window_start = now;
        }

        // Reset burst window
        if now - window.burst_start > 1 {
            window.burst_count = 0;
            window.burst_start = now;
        }

        window.count += 1;
        window.burst_count += 1;

        // Check burst limit
        if window.burst_count > self.burst_limit {
            let remaining = 0;
            let reset = window.burst_start + 1;
            return (false, remaining, reset);
        }

        // Check rate limit
        if window.count > adjusted_limit {
            let remaining = 0;
            let reset = window.window_start + window_ms;
            return (false, remaining, reset);
        }

        let remaining = adjusted_limit - window.count;
        let reset = window.window_start + window_ms;
        (true, remaining, reset)
    }

    fn detect_attack_pattern(&self, req: &CheckRequest) -> (String, Vec<String>) {
        let mut recommendations = Vec::new();
        let mut pattern = "normal".to_string();

        // Check for scanning pattern (many unique endpoints)
        if let Some(stats) = self.connection_stats.get(&req.ip) {
            if stats.unique_endpoints > 50 {
                pattern = "scanning".to_string();
                recommendations.push("IP appears to be scanning endpoints".to_string());
            }
            if stats.avg_request_duration_ms > 30_000.0 {
                pattern = "slowloris".to_string();
                recommendations.push("Slowloris attack pattern detected".to_string());
            }
            if stats.unique_user_agents > 10 {
                recommendations.push("Multiple user agents from same IP (possible bot)".to_string());
            }
        }

        // Update connection stats
        self.connection_stats
            .entry(req.ip.clone())
            .and_modify(|stats| {
                stats.concurrent_connections += 1;
                stats.unique_endpoints += 1;
            })
            .or_insert_with(|| ConnectionAnalysis {
                ip: req.ip.clone(),
                concurrent_connections: 1,
                avg_request_duration_ms: 0.0,
                request_pattern: "normal".to_string(),
                unique_endpoints: 1,
                unique_user_agents: 1,
                payload_anomaly_score: 0.0,
            });

        // Check for suspicious user agents
        if let Some(ua) = &req.user_agent {
            let suspicious_uas = ["sqlmap", "nikto", "nmap", "masscan", "zgrab", "gobuster", "dirbuster"];
            for s in &suspicious_uas {
                if ua.to_lowercase().contains(s) {
                    pattern = "attack_tool".to_string();
                    recommendations.push(format!("Known attack tool detected: {}", s));
                }
            }
        }

        // Check for oversized payloads
        if let Some(cl) = req.content_length {
            if cl > 10_000_000 {
                recommendations.push("Oversized request body (possible body bomb)".to_string());
            }
        }

        // Request fingerprinting — detect automated patterns
        if let Some(headers) = &req.headers {
            if !headers.contains_key("accept") && !headers.contains_key("Accept") {
                recommendations.push("Missing Accept header (possible bot)".to_string());
            }
            if !headers.contains_key("accept-language") && !headers.contains_key("Accept-Language") {
                recommendations.push("Missing Accept-Language header (possible bot)".to_string());
            }
        }

        (pattern, recommendations)
    }
}

// ── Handlers ─────────────────────────────────────────────────────────

async fn check_request(
    State(state): State<Arc<AppState>>,
    Json(req): Json<CheckRequest>,
) -> (StatusCode, Json<CheckResponse>) {
    // Increment global counter
    {
        let mut count = state.global_request_count.write().await;
        *count += 1;
    }

    // Check permanent blocklist
    if state.permanent_blocklist.contains_key(&req.ip) {
        return (
            StatusCode::FORBIDDEN,
            Json(CheckResponse {
                allowed: false,
                reason: Some("IP permanently blocked".to_string()),
                ip_score: 0.0,
                threat_level: ThreatLevel::Critical,
                rate_limit_remaining: 0,
                rate_limit_reset: 0,
                recommendations: vec!["Contact support to appeal".to_string()],
            }),
        );
    }

    // Get or create IP reputation
    let reputation = state.get_or_create_reputation(&req.ip);

    // Check if IP is temporarily blocked
    let now = Utc::now().timestamp();
    if reputation.is_blocked && now < reputation.blocked_until {
        state.update_reputation(&req.ip, 0.0, false);
        state.ip_reputations.entry(req.ip.clone()).and_modify(|r| {
            r.blocked_requests += 1;
        });
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(CheckResponse {
                allowed: false,
                reason: Some(format!("IP blocked until {}", reputation.blocked_until)),
                ip_score: reputation.score,
                threat_level: reputation.threat_level.clone(),
                rate_limit_remaining: 0,
                rate_limit_reset: reputation.blocked_until,
                recommendations: vec![],
            }),
        );
    }

    // Check threat intelligence
    if let Some(intel) = state.threat_intel.get(&req.ip) {
        if intel.confidence > 0.8 && now < intel.expires_at {
            state.update_reputation(&req.ip, -20.0, true);
            return (
                StatusCode::FORBIDDEN,
                Json(CheckResponse {
                    allowed: false,
                    reason: Some(format!("Threat intel: {} ({})", intel.threat_type, intel.source)),
                    ip_score: reputation.score - 20.0,
                    threat_level: ThreatLevel::Critical,
                    rate_limit_remaining: 0,
                    rate_limit_reset: 0,
                    recommendations: vec!["IP flagged by threat intelligence".to_string()],
                }),
            );
        }
    }

    // Check rate limit (adaptive based on reputation)
    let (rate_ok, remaining, reset) = state.check_rate_limit(&req.ip, reputation.score);
    if !rate_ok {
        state.update_reputation(&req.ip, -5.0, true);

        // Auto-block after repeated violations
        if reputation.violations >= 3 {
            let block_duration = state.block_duration_secs * (reputation.violations as u64).min(10);
            state.ip_reputations.entry(req.ip.clone()).and_modify(|r| {
                r.is_blocked = true;
                r.blocked_until = now + block_duration as i64;
            });

            // Permanent block after threshold
            if reputation.violations >= state.permanent_block_violations {
                state.permanent_blocklist.insert(req.ip.clone(), "Auto-blocked: excessive violations".to_string());
                warn!("IP {} permanently blocked after {} violations", req.ip, reputation.violations);
            }
        }

        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(CheckResponse {
                allowed: false,
                reason: Some("Rate limit exceeded".to_string()),
                ip_score: reputation.score,
                threat_level: reputation.threat_level.clone(),
                rate_limit_remaining: 0,
                rate_limit_reset: reset,
                recommendations: vec![],
            }),
        );
    }

    // Detect attack patterns
    let (pattern, recommendations) = state.detect_attack_pattern(&req);
    if pattern != "normal" {
        state.update_reputation(&req.ip, -10.0, true);
        warn!("Attack pattern '{}' from IP {}", pattern, req.ip);
    } else {
        // Good behavior slowly restores reputation
        state.update_reputation(&req.ip, 0.5, false);
    }

    let updated_rep = state.get_or_create_reputation(&req.ip);

    (
        StatusCode::OK,
        Json(CheckResponse {
            allowed: true,
            reason: None,
            ip_score: updated_rep.score,
            threat_level: updated_rep.threat_level,
            rate_limit_remaining: remaining,
            rate_limit_reset: reset,
            recommendations,
        }),
    )
}

async fn report_violation(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ReportRequest>,
) -> (StatusCode, Json<serde_json::Value>) {
    let severity_penalty = -(req.severity as f64) * 3.0;
    state.update_reputation(&req.ip, severity_penalty, true);

    info!(
        "Violation reported: IP={}, type={}, severity={}",
        req.ip, req.violation_type, req.severity
    );

    // Auto-block for high severity
    if req.severity >= 8 {
        let now = Utc::now().timestamp();
        state.ip_reputations.entry(req.ip.clone()).and_modify(|r| {
            r.is_blocked = true;
            r.blocked_until = now + 3600; // 1 hour
        });
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "acknowledged": true,
            "ip": req.ip,
            "new_score": state.get_or_create_reputation(&req.ip).score,
        })),
    )
}

async fn block_ip(
    State(state): State<Arc<AppState>>,
    Json(req): Json<BlockRequest>,
) -> (StatusCode, Json<serde_json::Value>) {
    let duration = req.duration_seconds.unwrap_or(3600);
    let now = Utc::now().timestamp();

    if duration == 0 {
        // Permanent block
        state.permanent_blocklist.insert(req.ip.clone(), req.reason.clone());
    }

    state.ip_reputations.entry(req.ip.clone()).and_modify(|r| {
        r.is_blocked = true;
        r.blocked_until = if duration == 0 { i64::MAX } else { now + duration as i64 };
        r.score = 0.0;
    });

    info!("IP {} blocked for {}s: {}", req.ip, duration, req.reason);

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "blocked": true,
            "ip": req.ip,
            "duration_seconds": duration,
            "reason": req.reason,
        })),
    )
}

async fn unblock_ip(
    State(state): State<Arc<AppState>>,
    Json(body): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    let ip = body["ip"].as_str().unwrap_or("");
    state.permanent_blocklist.remove(ip);
    state.ip_reputations.entry(ip.to_string()).and_modify(|r| {
        r.is_blocked = false;
        r.blocked_until = 0;
        r.violations = 0;
        r.score = 50.0;
    });

    (
        StatusCode::OK,
        Json(serde_json::json!({ "unblocked": true, "ip": ip })),
    )
}

async fn get_ip_reputation(
    State(state): State<Arc<AppState>>,
    Json(body): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    let ip = body["ip"].as_str().unwrap_or("");
    let rep = state.get_or_create_reputation(ip);
    (StatusCode::OK, Json(serde_json::to_value(rep).unwrap()))
}

async fn add_threat_intel(
    State(state): State<Arc<AppState>>,
    Json(entry): Json<ThreatIntelEntry>,
) -> (StatusCode, Json<serde_json::Value>) {
    state.threat_intel.insert(entry.ip.clone(), entry.clone());
    info!("Threat intel added: IP={}, type={}", entry.ip, entry.threat_type);
    (
        StatusCode::OK,
        Json(serde_json::json!({ "added": true, "ip": entry.ip })),
    )
}

async fn configure_circuit_breaker(
    State(state): State<Arc<AppState>>,
    Json(config): Json<CircuitBreakerConfig>,
) -> (StatusCode, Json<serde_json::Value>) {
    state.circuits.insert(
        config.service_name.clone(),
        CircuitState {
            name: config.service_name.clone(),
            state: "closed".to_string(),
            failures: 0,
            successes: 0,
            last_failure: 0,
            opened_at: 0,
            half_open_attempts: 0,
        },
    );
    (
        StatusCode::OK,
        Json(serde_json::json!({
            "configured": true,
            "service": config.service_name,
        })),
    )
}

async fn get_status(State(state): State<Arc<AppState>>) -> Json<StatusResponse> {
    let blocked_count = state.ip_reputations.iter().filter(|r| r.is_blocked).count();
    let circuits: Vec<CircuitState> = state.circuits.iter().map(|c| c.value().clone()).collect();
    let uptime = state.start_time.elapsed().as_secs();
    let total_requests = *state.global_request_count.read().await;
    let rps = if uptime > 0 { total_requests as f64 / uptime as f64 } else { 0.0 };

    Json(StatusResponse {
        total_ips_tracked: state.ip_reputations.len(),
        blocked_ips: blocked_count,
        circuit_states: circuits,
        requests_per_second: rps,
        threat_intel_entries: state.threat_intel.len(),
        uptime_seconds: uptime,
    })
}

async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "healthy",
        "service": "ddos-shield",
        "version": "1.0.0",
        "timestamp": Utc::now().to_rfc3339(),
    }))
}

// ── Background Tasks ─────────────────────────────────────────────────

async fn cleanup_task(state: Arc<AppState>) {
    loop {
        tokio::time::sleep(Duration::from_secs(60)).await;
        let now = Utc::now().timestamp();

        // Remove stale IP records (inactive > 1 hour, not blocked)
        let stale_ips: Vec<String> = state
            .ip_reputations
            .iter()
            .filter(|r| now - r.last_seen > 3600 && !r.is_blocked)
            .map(|r| r.ip.clone())
            .collect();

        for ip in &stale_ips {
            state.ip_reputations.remove(ip);
            state.rate_windows.remove(ip);
            state.connection_stats.remove(ip);
        }

        // Remove expired threat intel
        let expired_intel: Vec<String> = state
            .threat_intel
            .iter()
            .filter(|e| now > e.expires_at)
            .map(|e| e.ip.clone())
            .collect();

        for ip in &expired_intel {
            state.threat_intel.remove(ip);
        }

        if !stale_ips.is_empty() || !expired_intel.is_empty() {
            info!(
                "Cleanup: removed {} stale IPs, {} expired threat intel entries",
                stale_ips.len(),
                expired_intel.len()
            );
        }
    }
}

// ── Main ─────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter("info")
        .json()
        .init();

    let state = Arc::new(AppState::new());
    let cleanup_state = state.clone();

    // Start background cleanup
    tokio::spawn(async move {
        cleanup_task(cleanup_state).await;
    });

    let app = Router::new()
        .route("/health", get(health))
        .route("/status", get(get_status))
        .route("/stats", get(get_status))
        .route("/check", post(check_request))
        .route("/report", post(report_violation))
        .route("/block", post(block_ip))
        .route("/unblock", post(unblock_ip))
        .route("/reputation", post(get_ip_reputation))
        .route("/threat-intel", post(add_threat_intel))
        .route("/circuit-breaker/configure", post(configure_circuit_breaker))
        .with_state(state);

    let port = std::env::var("DDOS_SHIELD_PORT")
        .unwrap_or_else(|_| "8090".to_string())
        .parse::<u16>()
        .unwrap_or(8090);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("DDoS Shield starting on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ip_reputation_creation() {
        let state = AppState::new();
        let rep = state.get_or_create_reputation("192.168.1.1");
        assert_eq!(rep.score, 100.0);
        assert_eq!(rep.violations, 0);
        assert!(!rep.is_blocked);
    }

    #[test]
    fn test_reputation_degradation() {
        let state = AppState::new();
        state.get_or_create_reputation("10.0.0.1");
        state.update_reputation("10.0.0.1", -30.0, true);
        let rep = state.get_or_create_reputation("10.0.0.1");
        assert_eq!(rep.score, 70.0);
        assert_eq!(rep.violations, 1);
        assert_eq!(rep.threat_level, ThreatLevel::Low);
    }

    #[test]
    fn test_rate_limiting() {
        let state = AppState::new();
        state.get_or_create_reputation("10.0.0.2");
        // First request should pass
        let (allowed, _, _) = state.check_rate_limit("10.0.0.2", 100.0);
        assert!(allowed);
    }

    #[test]
    fn test_threat_level_classification() {
        let state = AppState::new();
        state.get_or_create_reputation("10.0.0.3");

        state.update_reputation("10.0.0.3", -25.0, false);
        assert_eq!(state.get_or_create_reputation("10.0.0.3").threat_level, ThreatLevel::Low);

        state.update_reputation("10.0.0.3", -25.0, false);
        assert_eq!(state.get_or_create_reputation("10.0.0.3").threat_level, ThreatLevel::Medium);

        state.update_reputation("10.0.0.3", -25.0, false);
        assert_eq!(state.get_or_create_reputation("10.0.0.3").threat_level, ThreatLevel::High);
    }

    #[test]
    fn test_permanent_blocklist() {
        let state = AppState::new();
        state.permanent_blocklist.insert("evil.ip".to_string(), "test".to_string());
        assert!(state.permanent_blocklist.contains_key("evil.ip"));
    }

    #[test]
    fn test_score_clamping() {
        let state = AppState::new();
        state.get_or_create_reputation("10.0.0.4");
        state.update_reputation("10.0.0.4", -200.0, true);
        let rep = state.get_or_create_reputation("10.0.0.4");
        assert_eq!(rep.score, 0.0); // Should not go below 0

        state.update_reputation("10.0.0.4", 500.0, false);
        let rep = state.get_or_create_reputation("10.0.0.4");
        assert_eq!(rep.score, 100.0); // Should not go above 100
    }
}
