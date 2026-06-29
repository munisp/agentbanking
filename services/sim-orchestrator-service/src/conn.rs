/// Unified connectivity interface abstraction for the 54agent SIM Orchestrator.
///
/// This module defines `ConnInterface` — a unified enum that represents any
/// connectivity bearer (SIM slot or WiFi) that the orchestrator can select.
/// It replaces the SIM-only `select_best()` with `select_best_conn()` which
/// considers all available interfaces in a single pass.
///
/// # Selection priority
///
/// WiFi receives a priority bonus of +200 points when RSSI > -65 dBm.
/// This makes WiFi the preferred interface when signal is strong.
/// The bonus decreases linearly to 0 at -80 dBm, and WiFi is excluded
/// entirely when RSSI < -85 dBm (unusable signal).
///
/// # Fallback behaviour
///
/// If WiFi is not connected or scores below all SIM interfaces, the best
/// SIM slot is selected automatically. If all interfaces score 0, returns
/// `ConnInterface::None` to indicate no network is available.

use crate::probe::{SimReading, SimSlot};
use crate::wifi::WifiReading;
use serde::{Deserialize, Serialize};

/// A unified connectivity interface — either a SIM slot or the WiFi interface.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConnInterface {
    /// A cellular SIM slot (Physical SIM 1/2 or eSIM 1/2).
    Sim(SimSlot),
    /// The WiFi interface.
    Wifi,
    /// No interface available (all scored 0).
    None,
}

impl ConnInterface {
    /// Return a human-readable label for the interface.
    pub fn label(self) -> &'static str {
        match self {
            ConnInterface::Sim(slot) => slot.label(),
            ConnInterface::Wifi => "WIFI",
            ConnInterface::None => "NONE",
        }
    }

    /// Return true if this interface is a cellular SIM slot.
    pub fn is_cellular(self) -> bool {
        matches!(self, ConnInterface::Sim(_))
    }

    /// Return true if this is the WiFi interface.
    pub fn is_wifi(self) -> bool {
        matches!(self, ConnInterface::Wifi)
    }

    /// Return true if no interface is available.
    pub fn is_none(self) -> bool {
        matches!(self, ConnInterface::None)
    }
}

/// WiFi priority bonus constants.
///
/// WiFi gets a bonus of +200 points when RSSI is excellent (> -65 dBm).
/// The bonus scales linearly to 0 between -65 and -80 dBm.
/// Below -80 dBm, WiFi receives no bonus (but still competes on base score).
/// Below -85 dBm, WiFi is excluded from selection entirely.
const WIFI_PRIORITY_BONUS_MAX: u16 = 200;
const WIFI_BONUS_RSSI_EXCELLENT: i16 = -65; // full bonus above this
const WIFI_BONUS_RSSI_FLOOR: i16 = -80;     // bonus drops to 0 at this point
const WIFI_EXCLUDE_RSSI: i16 = -85;         // excluded below this

/// Compute the WiFi priority bonus based on RSSI.
/// Returns a value in the range 0–200.
fn wifi_priority_bonus(rssi_dbm: i16) -> u16 {
    if rssi_dbm < WIFI_EXCLUDE_RSSI {
        return 0; // too weak — no bonus
    }
    if rssi_dbm >= WIFI_BONUS_RSSI_EXCELLENT {
        return WIFI_PRIORITY_BONUS_MAX; // excellent signal — full bonus
    }
    if rssi_dbm <= WIFI_BONUS_RSSI_FLOOR {
        return 0; // below floor — no bonus
    }
    // Linear interpolation between floor and excellent
    // bonus = MAX * (rssi - floor) / (excellent - floor)
    let range = (WIFI_BONUS_RSSI_EXCELLENT - WIFI_BONUS_RSSI_FLOOR) as u16;
    let above_floor = (rssi_dbm - WIFI_BONUS_RSSI_FLOOR) as u16;
    WIFI_PRIORITY_BONUS_MAX * above_floor / range
}

/// Compute the base WiFi score (0–1000) from signal and latency metrics.
///
/// Score formula (total = 1000 base + up to 200 priority bonus):
///   Signal strength (RSSI dBm) : 400 points  (40%)
///   Latency to gateway         : 350 points  (35%)
///   Packet loss (implicit)     : 150 points  (15%)  — assumed 0% for WiFi
///   Connection status          : 100 points  (10%)
fn wifi_base_score(reading: &WifiReading) -> u16 {
    if !reading.connected {
        return 0;
    }
    if reading.rssi_dbm < WIFI_EXCLUDE_RSSI {
        return 0; // signal too weak to use
    }

    // RSSI scoring: -30 dBm (excellent) → 400 pts, -85 dBm → 0 pts
    // Linear: score = 400 * (rssi - (-85)) / (-30 - (-85))
    let rssi_clamped = reading.rssi_dbm.max(-85).min(-30);
    let rssi_above_min = (rssi_clamped - (-85)) as u32;
    let rssi_range = (-30_i16 - (-85_i16)) as u32; // 55
    let s_rssi = (400u32 * rssi_above_min / rssi_range) as u16;

    // Latency scoring (same thresholds as SIM scorer)
    let s_latency: u16 = match reading.gateway_latency_ms {
        0..=10 => 350,
        11..=30 => 315,  // 90%
        31..=50 => 280,  // 80%
        51..=100 => 210, // 60%
        101..=200 => 140, // 40%
        201..=500 => 70,  // 20%
        _ => 0,
    };

    // Packet loss: WiFi with gateway reachable assumed 0% loss → full 150 pts
    // If gateway ping failed (latency = 0xFFFF), loss assumed 100% → 0 pts
    let s_loss: u16 = if reading.gateway_latency_ms == 0xFFFF { 0 } else { 150 };

    // Connection status: connected = 100 pts
    let s_conn: u16 = 100;

    s_rssi + s_latency + s_loss + s_conn
}

/// Compute the total WiFi score including priority bonus.
/// Returns a value in the range 0–1200.
pub fn compute_wifi_score(reading: &mut WifiReading) -> u16 {
    let base = wifi_base_score(reading);
    if base == 0 {
        reading.score = 0;
        return 0;
    }
    let bonus = wifi_priority_bonus(reading.rssi_dbm);
    let total = base + bonus;
    reading.score = total;
    total
}

/// Result of a unified connectivity selection pass.
#[derive(Debug, Clone)]
pub struct ConnSelectionResult {
    /// The selected interface.
    pub interface: ConnInterface,
    /// Score of the selected interface (0–1200).
    pub score: u16,
    /// Whether WiFi was available during selection.
    pub wifi_available: bool,
    /// Whether WiFi was preferred over cellular.
    pub wifi_preferred: bool,
}

/// Select the best connectivity interface from all available SIM slots and WiFi.
///
/// This function replaces `scorer::select_best()` for platforms that have
/// both cellular and WiFi interfaces. It evaluates all 5 interfaces (4 SIM + 1 WiFi)
/// in a single pass and returns the winner.
///
/// # Arguments
/// - `sim_readings`: mutable array of 4 SIM readings (scores are written back)
/// - `wifi_reading`: mutable WiFi reading (score is written back)
///
/// # Returns
/// A `ConnSelectionResult` with the selected interface and metadata.
pub fn select_best_conn(
    sim_readings: &mut [SimReading; 4],
    wifi_reading: &mut WifiReading,
) -> ConnSelectionResult {
    use crate::scorer::compute_score;

    // Score all SIM slots
    for r in sim_readings.iter_mut() {
        r.score = compute_score(r);
        r.selected = false;
    }

    // Score WiFi
    let wifi_score = compute_wifi_score(wifi_reading);
    wifi_reading.selected = false;

    // Find best SIM
    let best_sim = sim_readings
        .iter()
        .enumerate()
        .max_by_key(|(_, r)| r.score);

    let (best_sim_idx, best_sim_score) = match best_sim {
        Some((idx, r)) => (idx, r.score),
        None => (0, 0),
    };

    let wifi_available = wifi_reading.connected;

    // Compare WiFi vs best SIM
    if wifi_score > best_sim_score {
        wifi_reading.selected = true;
        ConnSelectionResult {
            interface: ConnInterface::Wifi,
            score: wifi_score,
            wifi_available,
            wifi_preferred: true,
        }
    } else if best_sim_score > 0 {
        sim_readings[best_sim_idx].selected = true;
        let slot = sim_readings[best_sim_idx].slot;
        ConnSelectionResult {
            interface: ConnInterface::Sim(slot),
            score: best_sim_score,
            wifi_available,
            wifi_preferred: false,
        }
    } else {
        // All interfaces scored 0 — no network available
        ConnSelectionResult {
            interface: ConnInterface::None,
            score: 0,
            wifi_available,
            wifi_preferred: false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::probe::{SimReading, SimSlot};
    use crate::wifi::WifiReading;
    use heapless::String;

    fn make_sim(slot: SimSlot, rssi: u8, reg: u8, lat: u16, loss: u16) -> SimReading {
        SimReading {
            slot,
            carrier: String::try_from("TestCarrier").unwrap_or_default(),
            mcc_mnc: 62120,
            rssi,
            reg_status: reg,
            latency_ms: lat,
            packet_loss_x10: loss,
            score: 0,
            selected: false,
        }
    }

    fn make_wifi(connected: bool, rssi_dbm: i16, latency: u16) -> WifiReading {
        if !connected {
            return WifiReading::disconnected();
        }
        WifiReading {
            ssid: String::try_from("TestSSID").unwrap_or_default(),
            bssid: String::try_from("AA:BB:CC:DD:EE:FF").unwrap_or_default(),
            rssi_dbm,
            channel: 36,
            gateway_latency_ms: latency,
            ip_address: 0xC0A80164, // 192.168.1.100
            connected: true,
            score: 0,
            selected: false,
        }
    }

    #[test]
    fn test_wifi_preferred_when_strong() {
        let mut sims = [
            make_sim(SimSlot::Phys1, 26, 1, 55, 0),
            make_sim(SimSlot::Phys2, 22, 1, 90, 10),
            make_sim(SimSlot::ESim1, 15, 1, 280, 30),
            make_sim(SimSlot::ESim2, 10, 5, 450, 80),
        ];
        let mut wifi = make_wifi(true, -55, 8); // excellent WiFi

        let result = select_best_conn(&mut sims, &mut wifi);
        assert_eq!(result.interface, ConnInterface::Wifi);
        assert!(result.wifi_preferred);
        assert!(wifi.selected);
        assert!(!sims.iter().any(|s| s.selected));
    }

    #[test]
    fn test_sim_preferred_when_wifi_weak() {
        let mut sims = [
            make_sim(SimSlot::Phys1, 28, 1, 45, 0), // strong SIM
            make_sim(SimSlot::Phys2, 22, 1, 90, 10),
            make_sim(SimSlot::ESim1, 15, 1, 280, 30),
            make_sim(SimSlot::ESim2, 10, 5, 450, 80),
        ];
        let mut wifi = make_wifi(true, -88, 200); // very weak WiFi (below exclude threshold)

        let result = select_best_conn(&mut sims, &mut wifi);
        assert_eq!(result.interface, ConnInterface::Sim(SimSlot::Phys1));
        assert!(!result.wifi_preferred);
        assert!(sims[0].selected);
        assert!(!wifi.selected);
    }

    #[test]
    fn test_wifi_disconnected_falls_back_to_sim() {
        let mut sims = [
            make_sim(SimSlot::Phys1, 20, 1, 80, 5),
            make_sim(SimSlot::Phys2, 18, 1, 120, 15),
            make_sim(SimSlot::ESim1, 10, 1, 300, 40),
            make_sim(SimSlot::ESim2, 8, 5, 500, 100),
        ];
        let mut wifi = make_wifi(false, 0, 0xFFFF);

        let result = select_best_conn(&mut sims, &mut wifi);
        assert!(result.interface.is_cellular());
        assert!(!result.wifi_available);
        assert!(!wifi.selected);
    }

    #[test]
    fn test_no_network_returns_none() {
        let mut sims = [
            make_sim(SimSlot::Phys1, 99, 0, 0xFFFF, 1000), // unregistered
            make_sim(SimSlot::Phys2, 99, 0, 0xFFFF, 1000),
            make_sim(SimSlot::ESim1, 99, 0, 0xFFFF, 1000),
            make_sim(SimSlot::ESim2, 99, 0, 0xFFFF, 1000),
        ];
        let mut wifi = make_wifi(false, 0, 0xFFFF);

        let result = select_best_conn(&mut sims, &mut wifi);
        assert_eq!(result.interface, ConnInterface::None);
        assert_eq!(result.score, 0);
    }

    #[test]
    fn test_wifi_priority_bonus_excellent() {
        let bonus = wifi_priority_bonus(-55);
        assert_eq!(bonus, WIFI_PRIORITY_BONUS_MAX);
    }

    #[test]
    fn test_wifi_priority_bonus_at_floor() {
        let bonus = wifi_priority_bonus(-80);
        assert_eq!(bonus, 0);
    }

    #[test]
    fn test_wifi_priority_bonus_linear_midpoint() {
        // Midpoint between -65 and -80 is -72.5 → ~100 pts
        let bonus = wifi_priority_bonus(-72);
        assert!(bonus > 90 && bonus < 110, "Expected ~100, got {}", bonus);
    }

    #[test]
    fn test_wifi_excluded_below_threshold() {
        let mut wifi = make_wifi(true, -90, 50); // below -85 dBm
        let score = compute_wifi_score(&mut wifi);
        assert_eq!(score, 0);
    }

    #[test]
    fn test_conn_interface_labels() {
        assert_eq!(ConnInterface::Wifi.label(), "WIFI");
        assert_eq!(ConnInterface::Sim(SimSlot::Phys1).label(), "PHYS1");
        assert_eq!(ConnInterface::None.label(), "NONE");
    }
}
