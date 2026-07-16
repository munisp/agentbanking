/// Probe payload — the data structure sent to the 54agent platform after each
/// SIM probe cycle. Designed to be compact (< 512 bytes JSON) for low-bandwidth
/// modem connections and compatible with both std and no_std targets.

use heapless::String;
use serde::{Deserialize, Serialize};

/// SIM slot identifier — matches the physical/eSIM layout of the POS terminal.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum SimSlot {
    /// Physical SIM 1 (e.g. MTN Nigeria)
    Phys1 = 0,
    /// Physical SIM 2 (e.g. Airtel Nigeria)
    Phys2 = 1,
    /// eSIM 1 (e.g. Glo Nigeria)
    ESim1 = 2,
    /// eSIM 2 (e.g. 9mobile Nigeria)
    ESim2 = 3,
}

impl SimSlot {
    pub fn index(self) -> usize {
        self as usize
    }

    pub fn label(self) -> &'static str {
        match self {
            SimSlot::Phys1 => "PHYS1",
            SimSlot::Phys2 => "PHYS2",
            SimSlot::ESim1 => "ESIM1",
            SimSlot::ESim2 => "ESIM2",
        }
    }
}

/// Per-SIM signal measurement from a single probe cycle.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimReading {
    /// SIM slot identifier.
    pub slot: SimSlot,

    /// Carrier name (from AT+COPS or provisioned config), max 32 chars.
    /// Examples: "MTN", "Airtel", "Glo", "9mobile"
    pub carrier: heapless::String<32>,

    /// IMSI prefix (first 6 digits = MCC+MNC) for carrier identification.
    /// 0 if not available.
    pub mcc_mnc: u32,

    /// Received Signal Strength Indicator from AT+CSQ.
    /// Range: 0–31 (99 = unknown). Higher is better.
    /// Maps to dBm: rssi_dbm = -113 + (rssi * 2)
    pub rssi: u8,

    /// Network registration status from AT+CEREG.
    /// 0=not registered, 1=registered home, 2=searching,
    /// 3=denied, 4=unknown, 5=registered roaming
    pub reg_status: u8,

    /// Round-trip latency in milliseconds (ICMP-equivalent via AT+PING).
    /// 0xFFFF if probe failed.
    pub latency_ms: u16,

    /// Packet loss percentage × 10 (e.g. 150 = 15.0%).
    /// Measured over 3 probe packets.
    pub packet_loss_x10: u16,

    /// Computed score (0–1000, fixed-point ×10).
    /// Higher is better. Calculated by the scorer.
    pub score: u16,

    /// Whether this SIM was selected as the active interface for the next tx.
    pub selected: bool,
}

impl SimReading {
    /// Convert RSSI (0–31) to approximate dBm value.
    pub fn rssi_dbm(&self) -> i16 {
        if self.rssi == 99 {
            return -999; // unknown
        }
        -113 + (self.rssi as i16 * 2)
    }

    /// Return packet loss as a percentage (0.0–100.0 equivalent, ×10 fixed-point).
    pub fn packet_loss_pct(&self) -> u16 {
        self.packet_loss_x10 / 10
    }
}

/// Full probe payload sent to the platform after each probe cycle.
/// Serializes to JSON for the HTTP relay.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProbePayload {
    /// Agent code of the POS terminal (e.g. "AGT001").
    pub agent_code: heapless::String<16>,

    /// Terminal serial number / device ID.
    pub terminal_id: heapless::String<32>,

    /// UTC timestamp in seconds since Unix epoch.
    /// On FreeRTOS, derived from RTC or modem AT+CCLK.
    pub timestamp_utc: u64,

    /// GPS coordinates if available (lat × 1e6, lon × 1e6).
    /// Both 0 if GPS not available.
    pub lat_e6: i32,
    pub lon_e6: i32,

    /// Readings for all 4 SIM slots (always 4 entries, even if slot is absent).
    /// Absent slots have rssi=99, reg_status=0, score=0.
    pub readings: [SimReading; 4],

    /// Index of the selected SIM slot (0–3).
    pub selected_slot: u8,

    /// Firmware version of the orchestrator.
    pub fw_version: heapless::String<16>,
}

impl ProbePayload {
    /// Serialize to a JSON string using a stack-allocated buffer (max 2048 bytes).
    /// Returns None if the serialized payload exceeds the buffer.
    #[cfg(feature = "std")]
    pub fn to_json_string(&self) -> Option<heapless::String<2048>> {
        let json = serde_json::to_string(self).ok()?;
        heapless::String::try_from(json.as_str()).ok()
    }

    /// Return the selected SimReading.
    pub fn selected_reading(&self) -> &SimReading {
        &self.readings[self.selected_slot as usize]
    }
}

/// Batch of probe payloads accumulated in the relay ring buffer.
/// Sent to the platform as a JSON array.
#[derive(Debug, Serialize, Deserialize)]
pub struct ProbeBatch {
    pub payloads: heapless::Vec<ProbePayload, 10>,
}

impl ProbeBatch {
    pub fn new() -> Self {
        ProbeBatch {
            payloads: heapless::Vec::new(),
        }
    }

    pub fn push(&mut self, payload: ProbePayload) -> bool {
        self.payloads.push(payload).is_ok()
    }

    pub fn is_full(&self) -> bool {
        self.payloads.is_full()
    }

    pub fn len(&self) -> usize {
        self.payloads.len()
    }

    pub fn is_empty(&self) -> bool {
        self.payloads.is_empty()
    }

    pub fn clear(&mut self) {
        self.payloads.clear();
    }
}
