/// WiFi connectivity module for the 54agent SIM Orchestrator.
///
/// Adds WiFi as a first-class connectivity interface alongside the 4 SIM slots.
/// When WiFi is available and strong, it is preferred over cellular because:
///   - Lower latency (typically < 10ms vs 50–200ms for 4G)
///   - No per-MB data cost (important for high-volume transaction logs)
///   - Higher throughput for OTA updates
///
/// The WiFi interface participates in the unified `ConnInterface` selection
/// via `select_best_conn()` in `scorer.rs`. It receives a priority bonus of
/// +200 points when RSSI > -65 dBm, making it preferred over cellular by
/// default when signal is strong. This bonus drops to 0 when RSSI < -80 dBm.

use crate::hal::WifiHal;
use heapless::String;
use serde::{Deserialize, Serialize};

/// WiFi security protocol (informational, does not affect scoring).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WifiSecurity {
    Open,
    Wpa2Personal,
    Wpa2Enterprise,
    Wpa3,
    Unknown,
}

/// Per-WiFi-interface measurement from a single probe cycle.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WifiReading {
    /// SSID of the connected AP (max 32 chars). Empty if not connected.
    pub ssid: String<32>,

    /// BSSID of the connected AP as a hex string (e.g. "AA:BB:CC:DD:EE:FF").
    pub bssid: String<18>,

    /// RSSI in dBm (negative, e.g. -65). 0 if not connected.
    pub rssi_dbm: i16,

    /// WiFi channel number (1–14 for 2.4GHz, 36–165 for 5GHz). 0 if unknown.
    pub channel: u8,

    /// Round-trip latency to default gateway in milliseconds.
    /// 0xFFFF if ping failed or not connected.
    pub gateway_latency_ms: u16,

    /// IPv4 address as a u32 (big-endian). 0 if not connected.
    pub ip_address: u32,

    /// Whether the WiFi interface is connected to an AP.
    pub connected: bool,

    /// Computed score (0–1200, includes priority bonus). Set by scorer.
    pub score: u16,

    /// Whether this interface was selected as the active interface.
    pub selected: bool,
}

impl WifiReading {
    /// Create a "not connected" WiFi reading (all zeros, score = 0).
    pub fn disconnected() -> Self {
        WifiReading {
            ssid: String::new(),
            bssid: String::new(),
            rssi_dbm: 0,
            channel: 0,
            gateway_latency_ms: 0xFFFF,
            ip_address: 0,
            connected: false,
            score: 0,
            selected: false,
        }
    }

    /// Return signal quality as a human-readable label.
    pub fn signal_quality(&self) -> &'static str {
        if !self.connected { return "disconnected"; }
        match self.rssi_dbm {
            i16::MIN..=-80 => "poor",
            -79..=-70 => "fair",
            -69..=-60 => "good",
            -59..=-50 => "very good",
            _ => "excellent",
        }
    }

    /// Return the frequency band based on channel number.
    pub fn band(&self) -> &'static str {
        match self.channel {
            1..=14 => "2.4GHz",
            36..=165 => "5GHz",
            _ => "unknown",
        }
    }
}

/// Probe the WiFi interface using the provided HAL implementation.
///
/// Returns a `WifiReading` with all metrics populated.
/// If the WiFi interface is not connected, returns `WifiReading::disconnected()`.
pub fn probe_wifi<W: WifiHal>(hal: &mut W) -> WifiReading {
    if !hal.is_connected() {
        return WifiReading::disconnected();
    }

    let ssid = hal.ssid().unwrap_or_else(|_| String::new());
    let bssid_bytes = hal.bssid().unwrap_or([0u8; 6]);
    let rssi_dbm = hal.rssi_dbm().unwrap_or(-100);
    let channel = hal.channel().unwrap_or(0);
    let gateway_latency_ms = hal.gateway_latency_ms();
    let ip_address = hal.ip_address();

    // Format BSSID as hex string
    let mut bssid: String<18> = String::new();
    let _ = core::fmt::write(
        &mut bssid,
        format_args!(
            "{:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}",
            bssid_bytes[0], bssid_bytes[1], bssid_bytes[2],
            bssid_bytes[3], bssid_bytes[4], bssid_bytes[5]
        ),
    );

    WifiReading {
        ssid,
        bssid,
        rssi_dbm,
        channel,
        gateway_latency_ms,
        ip_address,
        connected: true,
        score: 0, // set by scorer
        selected: false,
    }
}

/// Simulate a WiFi probe cycle for testing / simulation mode.
/// Returns a reading with realistic values for a typical office WiFi.
#[cfg(feature = "std")]
pub fn simulate_wifi_probe(connected: bool) -> WifiReading {
    if !connected {
        return WifiReading::disconnected();
    }
    let mut r = WifiReading {
        ssid: String::try_from("54agent-Office-5G").unwrap_or_default(),
        bssid: String::try_from("AA:BB:CC:DD:EE:FF").unwrap_or_default(),
        rssi_dbm: -58,
        channel: 36,
        gateway_latency_ms: 8,
        ip_address: u32::from_be_bytes([192, 168, 1, 100]),
        connected: true,
        score: 0,
        selected: false,
    };
    r.score = 0; // will be set by scorer
    r
}
