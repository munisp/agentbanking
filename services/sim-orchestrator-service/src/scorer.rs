/// Fixed-point signal scorer for SIM interface selection.
///
/// All arithmetic uses integer math only — no floating-point unit (FPU) required.
/// This makes the scorer compatible with Cortex-M0/M0+ targets that lack an FPU.
///
/// Score formula (total = 1000 points):
///   Signal strength (RSSI)  : 400 points  (40%)
///   Latency                 : 350 points  (35%)
///   Packet loss             : 150 points  (15%)
///   Registration status     : 100 points  (10%)
///
/// A SIM that is not registered (reg_status ∉ {1, 5}) receives a score of 0
/// regardless of other metrics, since it cannot carry traffic.

use crate::probe::SimReading;

/// Weight constants (must sum to 1000).
const W_RSSI: u32 = 400;
const W_LATENCY: u32 = 350;
const W_LOSS: u32 = 150;
const W_REG: u32 = 100;

/// RSSI scoring table (AT+CSQ value → score out of 400).
/// AT+CSQ range: 0–31 (99 = unknown).
/// Maps linearly: 0 → 0 pts, 31 → 400 pts.
fn score_rssi(rssi: u8) -> u32 {
    if rssi == 99 {
        return 0; // unknown
    }
    let rssi = rssi.min(31) as u32;
    // Linear: (rssi / 31) * W_RSSI
    // Integer: rssi * W_RSSI / 31
    rssi * W_RSSI / 31
}

/// Latency scoring (milliseconds → score out of 350).
/// ≤ 50ms  → 350 pts (full)
/// ≤ 100ms → 280 pts
/// ≤ 200ms → 210 pts
/// ≤ 500ms → 140 pts
/// ≤ 1000ms→  70 pts
/// > 1000ms→   0 pts
/// 9999    →   0 pts (probe failed)
fn score_latency(latency_ms: u16) -> u32 {
    match latency_ms {
        0..=50 => W_LATENCY,
        51..=100 => W_LATENCY * 80 / 100,
        101..=200 => W_LATENCY * 60 / 100,
        201..=500 => W_LATENCY * 40 / 100,
        501..=1000 => W_LATENCY * 20 / 100,
        _ => 0,
    }
}

/// Packet loss scoring (loss × 10 → score out of 150).
/// 0%    → 150 pts (full)
/// 1–5%  → 120 pts
/// 6–10% →  90 pts
/// 11–20%→  45 pts
/// > 20% →   0 pts
fn score_packet_loss(loss_x10: u16) -> u32 {
    // loss_x10 is percentage × 10 (e.g. 150 = 15.0%)
    match loss_x10 {
        0 => W_LOSS,
        1..=50 => W_LOSS * 80 / 100,
        51..=100 => W_LOSS * 60 / 100,
        101..=200 => W_LOSS * 30 / 100,
        _ => 0,
    }
}

/// Registration status scoring (AT+CEREG stat → score out of 100).
/// 1 = registered home   → 100 pts
/// 5 = registered roaming→  70 pts (roaming may incur extra cost/latency)
/// 2 = searching         →   0 pts (not usable)
/// 0,3,4 = not registered→   0 pts
fn score_reg_status(stat: u8) -> u32 {
    match stat {
        1 => W_REG,           // registered, home network
        5 => W_REG * 70 / 100, // registered, roaming
        _ => 0,               // not registered — SIM is unusable
    }
}

/// Compute the composite score for a single SIM reading.
/// Returns a value in the range 0–1000.
///
/// If the SIM is not registered, returns 0 immediately (cannot carry traffic).
pub fn compute_score(reading: &SimReading) -> u16 {
    // Hard gate: unregistered SIM scores 0 regardless of signal
    if reading.reg_status != 1 && reading.reg_status != 5 {
        return 0;
    }

    let s_rssi = score_rssi(reading.rssi);
    let s_latency = score_latency(reading.latency_ms);
    let s_loss = score_packet_loss(reading.packet_loss_x10);
    let s_reg = score_reg_status(reading.reg_status);

    (s_rssi + s_latency + s_loss + s_reg) as u16
}

/// Score all 4 SIM readings and return the index of the best one.
/// Returns None if all SIMs score 0 (no network available).
pub fn select_best(readings: &mut [SimReading; 4]) -> Option<usize> {
    let mut best_idx = None;
    let mut best_score = 0u16;

    for (i, reading) in readings.iter_mut().enumerate() {
        let score = compute_score(reading);
        reading.score = score;
        if score > best_score {
            best_score = score;
            best_idx = Some(i);
        }
    }

    // Mark the selected SIM
    if let Some(idx) = best_idx {
        readings[idx].selected = true;
    }

    best_idx
}

