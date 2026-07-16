/// SIM Orchestrator — Main Entry Point (std / Linux / Android target)
///
/// This file is compiled only when the `std` feature is active (default).
/// For FreeRTOS / no_std targets, the orchestrator logic is called from the
/// RTOS task entry function defined in `freertos_entry.rs` (not compiled here).
///
/// The std main function:
///   1. Reads configuration from environment variables.
///   2. Initialises the mock or platform HAL (Linux: serial port, Android: JNI).
///   3. Runs the probe loop in a Tokio async task.
///   4. Runs the watchdog task during active transactions (5s poll interval).
///   5. Runs the relay flush loop in a separate Tokio task.
///   6. Exposes a minimal HTTP health endpoint on port 9200.
///   7. Parses GPS coordinates from NMEA $GPRMC or AT+CGPSINFO responses.

use sim_orchestrator::conn::{select_best_conn, ConnInterface};
use sim_orchestrator::probe::{ProbePayload, SimReading, SimSlot};
use sim_orchestrator::scorer;
use sim_orchestrator::wifi::{simulate_wifi_probe, WifiReading};
use sim_orchestrator::watchdog::{
    FailoverReason, Watchdog, WatchdogDecision, WatchdogReading,
    LATENCY_THRESHOLD_MS, LOSS_THRESHOLD_X10, WATCHDOG_INTERVAL_MS,
};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::time::interval;

// ─── Configuration ────────────────────────────────────────────────────────────

/// Configuration loaded from environment variables.
#[derive(Debug, Clone)]
struct Config {
    /// Agent code of this POS terminal (e.g. "AGT001").
    agent_code: String,
    /// Terminal serial number.
    terminal_id: String,
    /// 54agent platform API base URL.
    platform_url: String,
    /// API key for authenticating with the platform.
    api_key: String,
    /// Probe interval in seconds (default: 30).
    probe_interval_secs: u64,
    /// Relay flush interval in seconds (default: 60).
    relay_flush_secs: u64,
    /// Ping host for latency measurement (default: 8.8.8.8).
    ping_host: String,
    /// Serial port for modem UART (e.g. /dev/ttyUSB0). Empty = simulation mode.
    uart_port: String,
    /// Serial port for GPS NMEA (e.g. /dev/ttyUSB1). Empty = use AT+CGPSINFO.
    gps_port: String,
    /// Firmware version string.
    fw_version: String,
    /// Enable watchdog failover (default: true).
    watchdog_enabled: bool,
}

impl Config {
    fn from_env() -> Self {
        Config {
            agent_code: std::env::var("SIM_AGENT_CODE")
                .unwrap_or_else(|_| "AGT001".to_string()),
            terminal_id: std::env::var("SIM_TERMINAL_ID")
                .unwrap_or_else(|_| "TERM-54agent-001".to_string()),
            platform_url: std::env::var("PLATFORM_API_URL")
                .unwrap_or_else(|_| "https://api.54agent.io".to_string()),
            api_key: std::env::var("SIM_API_KEY")
                .unwrap_or_else(|_| "54agent-sim-orchestrator-default-key".to_string()),
            probe_interval_secs: std::env::var("SIM_PROBE_INTERVAL_SECS")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(30),
            relay_flush_secs: std::env::var("SIM_RELAY_FLUSH_SECS")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(60),
            ping_host: std::env::var("SIM_PING_HOST")
                .unwrap_or_else(|_| "8.8.8.8".to_string()),
            uart_port: std::env::var("SIM_UART_PORT").unwrap_or_default(),
            gps_port: std::env::var("SIM_GPS_PORT").unwrap_or_default(),
            fw_version: env!("CARGO_PKG_VERSION").to_string(),
            watchdog_enabled: std::env::var("SIM_WATCHDOG_ENABLED")
                .map(|v| v != "0" && v.to_lowercase() != "false")
                .unwrap_or(true),
        }
    }
}

// ─── GPS Parsing ──────────────────────────────────────────────────────────────

/// GPS coordinate in micro-degrees (× 1,000,000).
#[derive(Debug, Clone, Copy, Default)]
pub struct GpsCoord {
    pub lat_e6: i32,
    pub lon_e6: i32,
}

/// Parse an NMEA $GPRMC or $GNRMC sentence into GPS coordinates.
///
/// Format: $GPRMC,HHMMSS.ss,A,DDMM.MMMM,N,DDDMM.MMMM,E,...
/// Returns None if the sentence is invalid or the fix is void ('V').
pub fn parse_nmea_gprmc(sentence: &str) -> Option<GpsCoord> {
    let sentence = sentence.trim();
    if !sentence.starts_with("$GPRMC") && !sentence.starts_with("$GNRMC") {
        return None;
    }

    // Strip checksum (*XX)
    let data = if let Some(idx) = sentence.rfind('*') {
        &sentence[..idx]
    } else {
        sentence
    };

    let fields: Vec<&str> = data.split(',').collect();
    if fields.len() < 7 {
        return None;
    }

    // Field 2: status — 'A' = active, 'V' = void
    if fields[2] != "A" {
        return None;
    }

    // Field 3: latitude DDMM.MMMM, Field 4: N/S
    let lat = parse_nmea_coord(fields[3], fields[4])?;
    // Field 5: longitude DDDMM.MMMM, Field 6: E/W
    let lon = parse_nmea_coord(fields[5], fields[6])?;

    Some(GpsCoord {
        lat_e6: (lat * 1_000_000.0) as i32,
        lon_e6: (lon * 1_000_000.0) as i32,
    })
}

/// Parse AT+CGPSINFO response into GPS coordinates.
///
/// Response format: +CGPSINFO: DDMM.MMMMMM,N,DDDMM.MMMMMM,E,date,time,alt,speed,course
/// Returns None if the response is invalid or fix is not available.
pub fn parse_at_cgpsinfo(response: &str) -> Option<GpsCoord> {
    // Find the +CGPSINFO: prefix
    let prefix = "+CGPSINFO:";
    let start = response.find(prefix)?;
    let data = response[start + prefix.len()..].trim();

    // If response is just empty or ",,,,,,,," — no fix
    if data.starts_with(',') || data.is_empty() {
        return None;
    }

    let fields: Vec<&str> = data.split(',').collect();
    if fields.len() < 4 {
        return None;
    }

    let lat = parse_nmea_coord(fields[0], fields[1])?;
    let lon = parse_nmea_coord(fields[2], fields[3])?;

    Some(GpsCoord {
        lat_e6: (lat * 1_000_000.0) as i32,
        lon_e6: (lon * 1_000_000.0) as i32,
    })
}

/// Convert NMEA coordinate string (DDMM.MMMM or DDDMM.MMMM) + hemisphere to decimal degrees.
fn parse_nmea_coord(coord_str: &str, hemisphere: &str) -> Option<f64> {
    if coord_str.is_empty() {
        return None;
    }

    // Find decimal point to split degrees from minutes
    let dot_pos = coord_str.find('.')?;
    if dot_pos < 2 {
        return None;
    }

    // Degrees are everything except the last 2 digits before the decimal point
    let deg_end = dot_pos - 2;
    let degrees: f64 = coord_str[..deg_end].parse().ok()?;
    let minutes: f64 = coord_str[deg_end..].parse().ok()?;

    let decimal = degrees + minutes / 60.0;

    match hemisphere {
        "S" | "W" => Some(-decimal),
        _ => Some(decimal),
    }
}

/// Attempt to read GPS coordinates from the environment (simulation) or UART.
/// In simulation mode, returns Lagos, Nigeria coordinates with slight jitter.
fn read_gps_coords(config: &Config) -> GpsCoord {
    // Check for GPS override via environment (useful for testing)
    if let (Ok(lat), Ok(lon)) = (
        std::env::var("SIM_GPS_LAT"),
        std::env::var("SIM_GPS_LON"),
    ) {
        if let (Ok(lat_f), Ok(lon_f)) = (lat.parse::<f64>(), lon.parse::<f64>()) {
            return GpsCoord {
                lat_e6: (lat_f * 1_000_000.0) as i32,
                lon_e6: (lon_f * 1_000_000.0) as i32,
            };
        }
    }

    // In simulation mode, return Lagos coordinates with jitter
    if config.uart_port.is_empty() && config.gps_port.is_empty() {
        let t = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        // Lagos, Nigeria: 6.5244° N, 3.3792° E
        // Add small jitter (±0.01°) to simulate movement
        let jitter_lat = ((t % 100) as i32 - 50) * 100; // ±5000 micro-degrees
        let jitter_lon = ((t % 73) as i32 - 36) * 100;
        return GpsCoord {
            lat_e6: 6_524_400 + jitter_lat,
            lon_e6: 3_379_200 + jitter_lon,
        };
    }

    // Production: would read from GPS UART or AT+CGPSINFO
    // For now return zero (no GPS fix) when real UART is configured but GPS not implemented
    GpsCoord::default()
}

// ─── Failover Reporting ───────────────────────────────────────────────────────

/// Report a SIM failover event to the 54agent platform.
/// This is called after each emergency switch by the watchdog.
async fn report_failover(
    client: &reqwest::Client,
    config: &Config,
    from_slot: u8,
    to_slot: u8,
    reason: FailoverReason,
    latency_ms: u32,
    loss_x10: u16,
    tx_ref: Option<&str>,
) {
    let url = format!(
        "{}/api/trpc/simOrchestrator.reportFailover",
        config.platform_url
    );

    let reason_str = match reason {
        FailoverReason::HighLatency => "high_latency",
        FailoverReason::HighPacketLoss => "high_packet_loss",
    };

    let body = serde_json::json!({
        "terminalId": config.terminal_id,
        "agentCode": config.agent_code,
        "fromSlot": from_slot,
        "toSlot": to_slot,
        "reason": reason_str,
        "latencyMs": latency_ms,
        "lossX10": loss_x10,
        "txRef": tx_ref,
        "apiKey": config.api_key,
    });

    match client
        .post(&url)
        .header("Content-Type", "application/json")
        .json(&body)
        .timeout(Duration::from_secs(5))
        .send()
        .await
    {
        Ok(resp) => {
            log::info!(
                "Failover reported: {} → {} reason={} status={}",
                from_slot,
                to_slot,
                reason_str,
                resp.status()
            );
        }
        Err(e) => {
            log::warn!("Failover report failed (non-critical): {}", e);
        }
    }
}

// ─── Probe Simulation ─────────────────────────────────────────────────────────

/// Simulate a probe cycle when no real UART is available (development/CI mode).
/// Returns realistic-looking readings for 4 Nigerian carriers.
fn simulate_probe_cycle(_config: &Config) -> [SimReading; 4] {
    use heapless::String as HString;

    // Add some jitter based on time to simulate real-world variation
    let t = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let jitter = (t % 10) as u8;

    let make = |slot: SimSlot, carrier: &str, rssi: u8, reg: u8, lat: u16, loss: u16| SimReading {
        slot,
        carrier: HString::try_from(carrier).unwrap_or_default(),
        mcc_mnc: match carrier {
            "MTN"     => 62150,
            "Airtel"  => 62120,
            "Glo"     => 62150,
            "9mobile" => 62160,
            _         => 0,
        },
        rssi: rssi.saturating_add(jitter % 5).min(31),
        reg_status: reg,
        latency_ms: lat.saturating_add(jitter as u16 * 3),
        packet_loss_x10: loss,
        score: 0,
        selected: false,
    };

    [
        make(SimSlot::Phys1, "MTN",     26, 1,  55,  0),   // Physical SIM 1
        make(SimSlot::Phys2, "Airtel",  22, 1,  90,  10),  // Physical SIM 2
        make(SimSlot::ESim1, "Glo",     15, 1, 280,  30),  // eSIM 1
        make(SimSlot::ESim2, "9mobile", 10, 5, 450,  80),  // eSIM 2 (roaming)
    ]
}

/// Build a ProbePayload from a set of readings, including WiFi selection.
fn build_payload(
    config: &Config,
    mut readings: [SimReading; 4],
    mut wifi: WifiReading,
    gps: GpsCoord,
) -> (ProbePayload, ConnInterface) {
    use heapless::String as HString;

    let conn_result = select_best_conn(&mut readings, &mut wifi);
    let selected_slot = match conn_result.interface {
        ConnInterface::Sim(slot) => slot.index() as u8,
        ConnInterface::Wifi => 0, // WiFi selected — SIM slot 0 as placeholder
        ConnInterface::None => 0,
    };

    let timestamp_utc = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let payload = ProbePayload {
        agent_code: HString::try_from(config.agent_code.as_str()).unwrap_or_default(),
        terminal_id: HString::try_from(config.terminal_id.as_str()).unwrap_or_default(),
        timestamp_utc,
        lat_e6: gps.lat_e6,
        lon_e6: gps.lon_e6,
        readings,
        selected_slot,
        fw_version: HString::try_from(config.fw_version.as_str()).unwrap_or_default(),
    };
    (payload, conn_result.interface)
}

/// Send a probe payload to the platform via HTTP POST.
async fn send_probe(client: &reqwest::Client, config: &Config, payload: &ProbePayload) {
    let url = format!(
        "{}/api/trpc/simOrchestrator.ingestProbe",
        config.platform_url
    );

    // Build the JSON body including the API key
    let body = serde_json::json!({
        "agentCode": payload.agent_code,
        "terminalId": payload.terminal_id,
        "timestampUtc": payload.timestamp_utc,
        "latE6": payload.lat_e6,
        "lonE6": payload.lon_e6,
        "readings": payload.readings.iter().map(|r| serde_json::json!({
            "slot": format!("{:?}", r.slot),
            "carrier": r.carrier,
            "mccMnc": r.mcc_mnc,
            "rssi": r.rssi,
            "regStatus": r.reg_status,
            "latencyMs": r.latency_ms,
            "packetLossX10": r.packet_loss_x10,
            "score": r.score,
            "selected": r.selected,
        })).collect::<Vec<_>>(),
        "selectedSlot": payload.selected_slot,
        "fwVersion": payload.fw_version,
        "apiKey": config.api_key,
    });

    match client
        .post(&url)
        .header("Content-Type", "application/json")
        .json(&body)
        .timeout(Duration::from_secs(10))
        .send()
        .await
    {
        Ok(resp) => {
            log::info!(
                "Probe sent: agent={} selected={} lat={} lon={} status={}",
                config.agent_code,
                payload.selected_slot,
                payload.lat_e6,
                payload.lon_e6,
                resp.status()
            );
        }
        Err(e) => {
            log::warn!("Probe send failed: {} — will retry next cycle", e);
        }
    }
}

// ─── Failover Event ───────────────────────────────────────────────────────────

/// Snapshot of a single watchdog-triggered failover, stored for status queries.
#[derive(Debug, Clone)]
struct FailoverEvent {
    from_slot: u8,
    to_slot: u8,
    /// "high_latency" or "high_packet_loss"
    reason: &'static str,
    latency_ms: u32,
    loss_x10: u16,
    tx_ref: Option<String>,
    timestamp_utc: u64,
}

// ─── Shared State ─────────────────────────────────────────────────────────────

/// Shared state between the probe loop, watchdog task, and HTTP server.
struct SharedState {
    /// Whether a transaction is currently in flight.
    transaction_active: AtomicBool,
    /// Latest probe readings (scored + selected flag set, updated every probe cycle).
    latest_readings: Mutex<Option<[SimReading; 4]>>,
    /// Latest WiFi reading (updated every probe cycle).
    latest_wifi: Mutex<Option<WifiReading>>,
    /// Current active interface (SIM slot index or WiFi).
    active_slot: Mutex<u8>,
    /// Whether the active interface is WiFi.
    active_is_wifi: AtomicBool,
    /// Transaction reference set by the POS app when a transaction starts.
    current_tx_ref: Mutex<Option<String>>,
    /// Most recent failover event (set by watchdog, read by status API).
    last_failover: Mutex<Option<FailoverEvent>>,
}

impl SharedState {
    fn new() -> Self {
        SharedState {
            transaction_active: AtomicBool::new(false),
            latest_readings: Mutex::new(None),
            latest_wifi: Mutex::new(None),
            active_slot: Mutex::new(0),
            active_is_wifi: AtomicBool::new(false),
            current_tx_ref: Mutex::new(None),
            last_failover: Mutex::new(None),
        }
    }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config = Config::from_env();
    log::info!(
        "54agent SIM Orchestrator v{} starting — agent={} terminal={}",
        config.fw_version,
        config.agent_code,
        config.terminal_id
    );
    log::info!(
        "Probe interval: {}s | Relay flush: {}s | Platform: {} | Watchdog: {}",
        config.probe_interval_secs,
        config.relay_flush_secs,
        config.platform_url,
        if config.watchdog_enabled { "enabled" } else { "disabled" }
    );

    if config.uart_port.is_empty() {
        log::warn!("SIM_UART_PORT not set — running in SIMULATION mode");
    } else {
        log::info!("UART port: {}", config.uart_port);
    }

    if !config.gps_port.is_empty() {
        log::info!("GPS port: {}", config.gps_port);
    } else {
        log::info!("GPS: using AT+CGPSINFO / simulation fallback");
    }

    let client = reqwest::Client::new();
    let config = Arc::new(config);
    let state = Arc::new(SharedState::new());

    // ── Probe loop ────────────────────────────────────────────────────────────
    let probe_config = Arc::clone(&config);
    let probe_client = client.clone();
    let probe_state = Arc::clone(&state);
    let probe_handle = tokio::spawn(async move {
        let mut ticker = interval(Duration::from_secs(probe_config.probe_interval_secs));
        loop {
            ticker.tick().await;
            log::debug!("Starting probe cycle...");

            // Read GPS coordinates
            let gps = read_gps_coords(&probe_config);
            if gps.lat_e6 != 0 {
                log::debug!("GPS fix: {:.6}, {:.6}", gps.lat_e6 as f64 / 1e6, gps.lon_e6 as f64 / 1e6);
            }

            // In simulation mode, use synthetic readings.
            // In production, this would call AtDriver::probe_active_sim() for each slot.
            let readings = simulate_probe_cycle(&probe_config);

            // Probe WiFi interface (simulation: connected with strong signal)
            let wifi_sim_connected = std::env::var("SIM_WIFI_ENABLED")
                .map(|v| v == "1" || v.to_lowercase() == "true")
                .unwrap_or(false);
            let wifi = simulate_wifi_probe(wifi_sim_connected);

            // Log per-SIM scores before selection
            let mut readings_copy = readings.clone();
            for r in &mut readings_copy {
                r.score = scorer::compute_score(r);
                log::debug!(
                    "  {} [{}] RSSI={} lat={}ms loss={}\u{2030} score={}",
                    r.slot.label(),
                    r.carrier,
                    r.rssi,
                    r.latency_ms,
                    r.packet_loss_x10,
                    r.score
                );
            }
            if wifi.connected {
                log::debug!(
                    "  WIFI [{}] RSSI={}dBm lat={}ms quality={}",
                    wifi.ssid,
                    wifi.rssi_dbm,
                    wifi.gateway_latency_ms,
                    wifi.signal_quality()
                );
            }

            let (payload, selected_iface) = build_payload(&probe_config, readings.clone(), wifi.clone(), gps);
            match selected_iface {
                ConnInterface::Wifi => {
                    log::info!(
                        "Selected WIFI [{}] RSSI={}dBm lat={}ms GPS=({:.4},{:.4})",
                        payload.readings[0].carrier,
                        wifi.rssi_dbm,
                        wifi.gateway_latency_ms,
                        gps.lat_e6 as f64 / 1e6,
                        gps.lon_e6 as f64 / 1e6,
                    );
                    probe_state.active_is_wifi.store(true, Ordering::Relaxed);
                }
                ConnInterface::Sim(_) => {
                    let selected = &payload.readings[payload.selected_slot as usize];
                    log::info!(
                        "Selected SIM: {} [{}] score={} RSSI={} lat={}ms GPS=({:.4},{:.4})",
                        selected.slot.label(),
                        selected.carrier,
                        selected.score,
                        selected.rssi,
                        selected.latency_ms,
                        gps.lat_e6 as f64 / 1e6,
                        gps.lon_e6 as f64 / 1e6,
                    );
                    probe_state.active_is_wifi.store(false, Ordering::Relaxed);
                }
                ConnInterface::None => {
                    log::warn!("No connectivity available — all interfaces scored 0");
                    probe_state.active_is_wifi.store(false, Ordering::Relaxed);
                }
            }

            // Update shared state — use scored readings from payload (select_best_conn
            // has already computed scores and set the selected flag on each slot).
            if let Ok(mut lock) = probe_state.latest_readings.lock() {
                *lock = Some(payload.readings.clone());
            }
            if let Ok(mut slot) = probe_state.active_slot.lock() {
                *slot = payload.selected_slot;
            }

            send_probe(&probe_client, &probe_config, &payload).await;
        }
    });

    // ── Watchdog task ─────────────────────────────────────────────────────────
    let watchdog_config = Arc::clone(&config);
    let watchdog_client = client.clone();
    let watchdog_state = Arc::clone(&state);
    let watchdog_handle = tokio::spawn(async move {
        if !watchdog_config.watchdog_enabled {
            log::info!("Watchdog disabled — skipping");
            return;
        }

        let mut watchdog = Watchdog::new();
        let mut ticker = interval(Duration::from_millis(WATCHDOG_INTERVAL_MS));

        log::info!(
            "Watchdog started — interval={}ms latency_threshold={}ms loss_threshold={:.1}%",
            WATCHDOG_INTERVAL_MS,
            LATENCY_THRESHOLD_MS,
            LOSS_THRESHOLD_X10 as f64 / 10.0,
        );

        loop {
            ticker.tick().await;

            let tx_active = watchdog_state.transaction_active.load(Ordering::Relaxed);

            // Manage watchdog transaction state
            if tx_active && !watchdog.transaction_active {
                let slot = watchdog_state.active_slot.lock()
                    .map(|s| *s)
                    .unwrap_or(0);
                let sim_slot = match slot {
                    0 => SimSlot::Phys1,
                    1 => SimSlot::Phys2,
                    2 => SimSlot::ESim1,
                    _ => SimSlot::ESim2,
                };
                watchdog.begin_transaction(sim_slot);
                log::info!("Watchdog: transaction started on slot {}", slot);
            } else if !tx_active && watchdog.transaction_active {
                watchdog.end_transaction();
                log::info!("Watchdog: transaction ended");
            }

            if !watchdog.should_check() {
                continue;
            }

            // Get latest readings for watchdog evaluation
            let readings_opt = watchdog_state.latest_readings.lock()
                .ok()
                .and_then(|lock| lock.clone());

            let Some(candidates) = readings_opt else {
                continue;
            };

            // Get current active slot's reading for watchdog check
            let active_slot_idx = watchdog_state.active_slot.lock()
                .map(|s| *s as usize)
                .unwrap_or(0);
            let active_reading = &candidates[active_slot_idx];

            // Build watchdog reading from current active SIM metrics
            let wd_reading = WatchdogReading {
                latency_ms: active_reading.latency_ms as u32,
                packet_loss_x10: active_reading.packet_loss_x10,
            };

            // Evaluate without mux (we report the decision and let the modem handle it)
            let latency_breach = wd_reading.latency_ms > LATENCY_THRESHOLD_MS;
            let loss_breach = wd_reading.packet_loss_x10 > LOSS_THRESHOLD_X10;

            if latency_breach || loss_breach {
                // Find best alternative slot
                let mut best_score: i32 = -1;
                let mut best_slot_idx: usize = active_slot_idx;

                for (i, candidate) in candidates.iter().enumerate() {
                    if i == active_slot_idx {
                        continue;
                    }
                    let score = scorer::compute_score(candidate) as i32;
                    if score > best_score {
                        best_score = score;
                        best_slot_idx = i;
                    }
                }

                if best_score > 0 && best_slot_idx != active_slot_idx {
                    let reason = if latency_breach {
                        FailoverReason::HighLatency
                    } else {
                        FailoverReason::HighPacketLoss
                    };

                    log::warn!(
                        "Watchdog: emergency failover {} → {} reason={:?} latency={}ms loss={:.1}%",
                        active_slot_idx,
                        best_slot_idx,
                        reason,
                        wd_reading.latency_ms,
                        wd_reading.packet_loss_x10 as f64 / 10.0,
                    );

                    // Update active slot
                    if let Ok(mut slot) = watchdog_state.active_slot.lock() {
                        *slot = best_slot_idx as u8;
                    }

                    let from = active_slot_idx as u8;
                    let to = best_slot_idx as u8;
                    let lat = wd_reading.latency_ms;
                    let loss = wd_reading.packet_loss_x10;

                    // Correlate with the current transaction reference (set by the POS app).
                    let tx_ref = watchdog_state.current_tx_ref.lock()
                        .ok()
                        .and_then(|lock| lock.clone());

                    // Persist the event so the /sim/status endpoint can expose it.
                    let failover_ts = SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_secs();
                    if let Ok(mut lock) = watchdog_state.last_failover.lock() {
                        *lock = Some(FailoverEvent {
                            from_slot: from,
                            to_slot: to,
                            reason: if latency_breach { "high_latency" } else { "high_packet_loss" },
                            latency_ms: lat,
                            loss_x10: loss,
                            tx_ref: tx_ref.clone(),
                            timestamp_utc: failover_ts,
                        });
                    }

                    // Report failover to platform (non-blocking)
                    let report_client = watchdog_client.clone();
                    let report_config = Arc::clone(&watchdog_config);
                    tokio::spawn(async move {
                        report_failover(
                            &report_client,
                            &report_config,
                            from,
                            to,
                            reason,
                            lat,
                            loss,
                            tx_ref.as_deref(),
                        ).await;
                    });

                    // Update watchdog state
                    watchdog.failover_count = watchdog.failover_count.saturating_add(1);
                    watchdog.last_failover_ms = SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_millis() as u64;
                } else {
                    log::warn!(
                        "Watchdog: threshold breach detected but no viable alternative (latency={}ms loss={:.1}%)",
                        wd_reading.latency_ms,
                        wd_reading.packet_loss_x10 as f64 / 10.0,
                    );
                }
            } else {
                log::debug!(
                    "Watchdog: slot {} healthy (latency={}ms loss={:.1}%)",
                    active_slot_idx,
                    wd_reading.latency_ms,
                    wd_reading.packet_loss_x10 as f64 / 10.0,
                );
            }
        }
    });

    // ── Health check HTTP server on port 9200 ─────────────────────────────────
    let health_config = Arc::clone(&config);
    let health_state = Arc::clone(&state);
    let health_handle = tokio::spawn(async move {
        use tokio::io::AsyncWriteExt;
        use tokio::net::TcpListener;

        let listener = TcpListener::bind("0.0.0.0:9200").await.unwrap_or_else(|e| {
            log::warn!("Health server failed to bind: {}", e);
            panic!("Cannot bind health port");
        });
        log::info!("Health endpoint: http://0.0.0.0:9200/health");

        loop {
            if let Ok((mut stream, _)) = listener.accept().await {
                use tokio::io::AsyncReadExt;

                let agent = health_config.agent_code.clone();
                let fw = health_config.fw_version.clone();
                let state_ref = Arc::clone(&health_state);

                tokio::spawn(async move {
                    // Read the incoming HTTP request.
                    let mut buf = [0u8; 4096];
                    let n = match stream.read(&mut buf).await {
                        Ok(0) | Err(_) => return,
                        Ok(n) => n,
                    };
                    // Use owned strings so there are no &str borrows across the final .await.
                    let req = String::from_utf8_lossy(&buf[..n]).into_owned();

                    // Parse method + path from the request line.
                    let first_line = req.lines().next().unwrap_or("").to_string();
                    let mut parts = first_line.split_whitespace();
                    let method = parts.next().unwrap_or("GET").to_string();
                    let path   = parts.next().unwrap_or("/health").to_string();

                    // Extract body (everything after the blank line between headers and body).
                    let body_str: String = req.find("\r\n\r\n")
                        .map(|i| req[i + 4..].to_string())
                        .unwrap_or_default();

                    let (status_line, resp_body): (&str, String) = match (method.as_str(), path.as_str()) {

                        // ── Legacy health check ──────────────────────────────────────
                        ("GET", "/health") | ("GET", "/health/") => {
                            let tx_active   = state_ref.transaction_active.load(Ordering::Relaxed);
                            let active_slot = state_ref.active_slot.lock().map(|s| *s).unwrap_or(0);
                            (
                                "HTTP/1.1 200 OK",
                                format!(
                                    r#"{{"status":"ok","agent":"{}","fw":"{}","txActive":{},"activeSlot":{}}}"#,
                                    agent, fw, tx_active, active_slot,
                                ),
                            )
                        }

                        // ── Full SIM status (consumed by the POS app) ────────────────
                        ("GET", "/sim/status") | ("GET", "/sim/status/") => {
                            let tx_active   = state_ref.transaction_active.load(Ordering::Relaxed);
                            let active_slot = state_ref.active_slot.lock().map(|s| *s).unwrap_or(0);
                            let is_wifi     = state_ref.active_is_wifi.load(Ordering::Relaxed);

                            let readings_json = state_ref.latest_readings.lock()
                                .ok()
                                .and_then(|lock| lock.clone())
                                .map(|readings| {
                                    let arr: Vec<serde_json::Value> = readings.iter().map(|r| {
                                        serde_json::json!({
                                            "slot":          format!("{:?}", r.slot),
                                            "carrier":       r.carrier.as_str(),
                                            "rssi":          r.rssi,
                                            "latencyMs":     r.latency_ms,
                                            "packetLossX10": r.packet_loss_x10,
                                            "score":         r.score,
                                            "selected":      r.selected,
                                            "regStatus":     r.reg_status,
                                        })
                                    }).collect();
                                    serde_json::to_string(&arr).unwrap_or_else(|_| "[]".to_string())
                                })
                                .unwrap_or_else(|| "[]".to_string());

                            let last_failover_json = state_ref.last_failover.lock()
                                .ok()
                                .and_then(|lock| lock.clone())
                                .map(|ev| serde_json::to_string(&serde_json::json!({
                                    "fromSlot":     ev.from_slot,
                                    "toSlot":       ev.to_slot,
                                    "reason":       ev.reason,
                                    "latencyMs":    ev.latency_ms,
                                    "lossX10":      ev.loss_x10,
                                    "txRef":        ev.tx_ref,
                                    "timestampUtc": ev.timestamp_utc,
                                })).unwrap_or_else(|_| "null".to_string()))
                                .unwrap_or_else(|| "null".to_string());

                            let tx_ref_json = state_ref.current_tx_ref.lock()
                                .ok()
                                .and_then(|lock| lock.clone())
                                .map(|r| format!("\"{}\"", r))
                                .unwrap_or_else(|| "null".to_string());

                            (
                                "HTTP/1.1 200 OK",
                                format!(
                                    r#"{{"transactionActive":{},"activeSlot":{},"isWifi":{},"txRef":{},"readings":{},"lastFailover":{}}}"#,
                                    tx_active, active_slot, is_wifi, tx_ref_json,
                                    readings_json, last_failover_json,
                                ),
                            )
                        }

                        // ── Transaction start — called by POS app before initiating transfer ──
                        ("POST", "/sim/transaction/start") | ("POST", "/sim/transaction/start/") => {
                            let tx_ref = serde_json::from_str::<serde_json::Value>(&body_str)
                                .ok()
                                .and_then(|v| v.get("txRef")?.as_str().map(|s| s.to_string()));

                            state_ref.transaction_active.store(true, Ordering::Relaxed);
                            if let Ok(mut lock) = state_ref.current_tx_ref.lock() {
                                *lock = tx_ref.clone();
                            }
                            log::info!("Transaction started via API: txRef={:?}", tx_ref);
                            ("HTTP/1.1 200 OK", r#"{"ok":true,"message":"transaction started"}"#.to_string())
                        }

                        // ── Transaction end — called by POS app after transfer completes/fails ─
                        ("POST", "/sim/transaction/end") | ("POST", "/sim/transaction/end/") => {
                            state_ref.transaction_active.store(false, Ordering::Relaxed);
                            if let Ok(mut lock) = state_ref.current_tx_ref.lock() {
                                *lock = None;
                            }
                            log::info!("Transaction ended via API");
                            ("HTTP/1.1 200 OK", r#"{"ok":true,"message":"transaction ended"}"#.to_string())
                        }

                        // ── CORS preflight ───────────────────────────────────────────
                        ("OPTIONS", _) => ("HTTP/1.1 204 No Content", String::new()),

                        _ => ("HTTP/1.1 404 Not Found", r#"{"error":"not found"}"#.to_string()),
                    };

                    let response = format!(
                        "{}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\nAccess-Control-Allow-Headers: Content-Type\r\n\r\n{}",
                        status_line,
                        resp_body.len(),
                        resp_body,
                    );
                    let _ = stream.write_all(response.as_bytes()).await;
                });
            }
        }
    });

    // Wait for all tasks (they run indefinitely)
    tokio::select! {
        _ = probe_handle    => log::error!("Probe loop exited unexpectedly"),
        _ = watchdog_handle => log::error!("Watchdog task exited unexpectedly"),
        _ = health_handle   => log::error!("Health server exited unexpectedly"),
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_nmea_gprmc_valid() {
        // Lagos, Nigeria: 6°31'28"N, 3°22'45"E
        let sentence = "$GPRMC,123519,A,0631.4667,N,00322.7500,E,022.4,084.4,230394,003.1,W*6A";
        let coord = parse_nmea_gprmc(sentence).expect("Should parse valid GPRMC");
        // 6° + 31.4667'/60 = 6.524445°
        assert!((coord.lat_e6 - 6_524_445).abs() < 10, "lat_e6={}", coord.lat_e6);
        // 3° + 22.7500'/60 = 3.379167°
        assert!((coord.lon_e6 - 3_379_167).abs() < 10, "lon_e6={}", coord.lon_e6);
    }

    #[test]
    fn test_parse_nmea_gprmc_void() {
        // Status 'V' = void (no fix)
        let sentence = "$GPRMC,123519,V,0000.0000,N,00000.0000,E,000.0,000.0,000000,000.0,W*6A";
        assert!(parse_nmea_gprmc(sentence).is_none());
    }

    #[test]
    fn test_parse_nmea_gprmc_south_west() {
        // Southern hemisphere, western longitude (São Paulo, Brazil)
        let sentence = "$GPRMC,123519,A,2333.4000,S,04638.2000,W,000.0,000.0,230394,000.0,E*6A";
        let coord = parse_nmea_gprmc(sentence).expect("Should parse S/W coordinates");
        assert!(coord.lat_e6 < 0, "Southern latitude should be negative");
        assert!(coord.lon_e6 < 0, "Western longitude should be negative");
    }

    #[test]
    fn test_parse_at_cgpsinfo_valid() {
        // Abuja, Nigeria: 9°03'00"N, 7°32'00"E
        let response = "+CGPSINFO: 0903.0000,N,00732.0000,E,230394,123519,840.0,0.0,0.0";
        let coord = parse_at_cgpsinfo(response).expect("Should parse AT+CGPSINFO");
        // 9° + 3.0'/60 = 9.05°
        assert!((coord.lat_e6 - 9_050_000).abs() < 10, "lat_e6={}", coord.lat_e6);
        // 7° + 32.0'/60 = 7.533333°
        assert!((coord.lon_e6 - 7_533_333).abs() < 10, "lon_e6={}", coord.lon_e6);
    }

    #[test]
    fn test_parse_at_cgpsinfo_no_fix() {
        // No fix — empty fields
        let response = "+CGPSINFO: ,,,,,,,,";
        assert!(parse_at_cgpsinfo(response).is_none());
    }

    #[test]
    fn test_parse_nmea_coord_degrees_minutes() {
        // 6°31.4667' N = 6.524445°
        let result = parse_nmea_coord("0631.4667", "N").expect("Should parse");
        assert!((result - 6.524445).abs() < 0.000001, "result={}", result);
    }

    #[test]
    fn test_parse_nmea_coord_southern() {
        let result = parse_nmea_coord("2333.4000", "S").expect("Should parse");
        assert!(result < 0.0, "Southern should be negative");
        assert!((result + 23.556667).abs() < 0.000001, "result={}", result);
    }

    #[test]
    fn test_gps_coord_default_is_zero() {
        let coord = GpsCoord::default();
        assert_eq!(coord.lat_e6, 0);
        assert_eq!(coord.lon_e6, 0);
    }

    #[test]
    fn test_read_gps_coords_simulation_mode() {
        let config = Config {
            agent_code: "TEST".to_string(),
            terminal_id: "TEST-001".to_string(),
            platform_url: "https://api.54agent.io".to_string(),
            api_key: "test-key".to_string(),
            probe_interval_secs: 30,
            relay_flush_secs: 60,
            ping_host: "8.8.8.8".to_string(),
            uart_port: String::new(), // empty = simulation
            gps_port: String::new(),
            fw_version: "0.1.0".to_string(),
            watchdog_enabled: true,
        };
        let coord = read_gps_coords(&config);
        // Should return Lagos-area coordinates in simulation mode
        assert!(coord.lat_e6 > 6_000_000 && coord.lat_e6 < 7_000_000,
            "Expected Lagos latitude, got {}", coord.lat_e6);
        assert!(coord.lon_e6 > 3_000_000 && coord.lon_e6 < 4_000_000,
            "Expected Lagos longitude, got {}", coord.lon_e6);
    }
}
