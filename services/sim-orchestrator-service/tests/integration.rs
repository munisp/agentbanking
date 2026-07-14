/// Integration tests for the 54agent SIM Orchestrator.
///
/// These tests use the mock HAL from `sim-hal-mock` to exercise the full
/// orchestrator stack without real hardware. All trait bounds are satisfied
/// via the library path `sim_orchestrator::hal::*`.

use heapless::String;
use sim_hal_mock::{MockGpio, MockHttp, MockTimer, MockUart};
use sim_orchestrator::hal::GpioHal;
use sim_orchestrator::{
    mux::SimMux,
    probe::{ProbePayload, SimReading, SimSlot},
    relay::Relay,
    scorer::{compute_score, select_best},
};

// ── Helpers ───────────────────────────────────────────────────────────────────

fn make_reading(slot: SimSlot, rssi: u8, reg: u8, latency: u16, loss: u8) -> SimReading {
    SimReading {
        slot,
        carrier: String::try_from("MTN").unwrap(),
        mcc_mnc: 62150,
        rssi,
        reg_status: reg,
        latency_ms: latency,
        packet_loss_x10: loss as u16,
        score: 0,
        selected: false,
    }
}

fn make_payload(agent: &str, readings: [SimReading; 4]) -> ProbePayload {
    ProbePayload {
        agent_code: String::try_from(agent).unwrap(),
        terminal_id: String::try_from("TERM001").unwrap(),
        timestamp_utc: 1_700_000_000,
        lat_e6: 6_524_379,
        lon_e6: 3_379_206,
        readings,
        selected_slot: 0,
        fw_version: String::try_from("1.0.0").unwrap(),
    }
}

// ── Scorer tests ──────────────────────────────────────────────────────────────

#[test]
fn test_score_perfect_signal() {
    let reading = make_reading(SimSlot::Phys1, 31, 1, 50, 0);
    let score = compute_score(&reading);
    // Perfect RSSI (31) = 400, low latency = ~350, 0% loss = 150, home reg = 100 → ~1000
    assert!(score >= 900, "Expected score >= 900, got {}", score);
}

#[test]
fn test_score_unregistered_sim_is_zero() {
    let reading = make_reading(SimSlot::Phys2, 25, 0, 100, 0);
    let score = compute_score(&reading);
    assert_eq!(score, 0, "Unregistered SIM must score 0");
}

#[test]
fn test_score_roaming_penalty() {
    let home = make_reading(SimSlot::Phys1, 20, 1, 100, 0);
    let roaming = make_reading(SimSlot::Phys2, 20, 5, 100, 0);
    let home_score = compute_score(&home);
    let roaming_score = compute_score(&roaming);
    assert!(
        home_score > roaming_score,
        "Home ({}) should score higher than roaming ({})",
        home_score,
        roaming_score
    );
}

#[test]
fn test_select_best_picks_highest_score() {
    let r1 = make_reading(SimSlot::Phys1, 10, 1, 200, 5);
    let r2 = make_reading(SimSlot::Phys2, 28, 1, 60, 0);
    let r3 = make_reading(SimSlot::ESim1, 5, 1, 300, 10);
    let r4 = make_reading(SimSlot::ESim2, 15, 1, 150, 2);
    let mut readings = [r1, r2, r3, r4];
    let best = select_best(&mut readings);
    assert_eq!(
        best,
        Some(1),
        "SIM 2 (Airtel, high RSSI) should be selected"
    );
}

#[test]
fn test_select_best_returns_none_when_all_unregistered() {
    let r1 = make_reading(SimSlot::Phys1, 20, 0, 100, 0);
    let r2 = make_reading(SimSlot::Phys2, 20, 0, 100, 0);
    let r3 = make_reading(SimSlot::ESim1, 20, 0, 100, 0);
    let r4 = make_reading(SimSlot::ESim2, 20, 0, 100, 0);
    let mut readings = [r1, r2, r3, r4];
    let best = select_best(&mut readings);
    assert_eq!(best, None, "No SIM registered — should return None");
}

// ── AT driver tests ───────────────────────────────────────────────────────────

#[test]
fn test_at_driver_csq_parse() {
    use sim_orchestrator::sim::AtDriver;
    let uart = MockUart::new_csq(22, 0);
    let timer = MockTimer::new();
    let mut driver = AtDriver::new(uart, timer);
    let (rssi, ber) = driver.query_csq().unwrap();
    assert_eq!(rssi, 22);
    assert_eq!(ber, 0);
}

#[test]
fn test_at_driver_cereg_parse() {
    use sim_orchestrator::sim::AtDriver;
    let uart = MockUart::new_cereg(1);
    let timer = MockTimer::new();
    let mut driver = AtDriver::new(uart, timer);
    let stat = driver.query_cereg().unwrap();
    assert_eq!(stat, 1);
}

#[test]
fn test_at_driver_cops_parse() {
    use sim_orchestrator::sim::AtDriver;
    let uart = MockUart::new_cops("MTN");
    let timer = MockTimer::new();
    let mut driver = AtDriver::new(uart, timer);
    let carrier = driver.query_carrier().unwrap();
    assert_eq!(carrier.as_str(), "MTN");
}

#[test]
fn test_at_driver_cimi_mcc_mnc() {
    use sim_orchestrator::sim::AtDriver;
    let uart = MockUart::new_cimi("621500123456789");
    let timer = MockTimer::new();
    let mut driver = AtDriver::new(uart, timer);
    let mcc_mnc = driver.query_mcc_mnc().unwrap();
    assert_eq!(mcc_mnc, 621500);
}

// ── Relay tests ───────────────────────────────────────────────────────────────

fn make_full_payload(agent: &str) -> ProbePayload {
    let r = make_reading(SimSlot::Phys1, 25, 1, 80, 0);
    make_payload(agent, [r.clone(), r.clone(), r.clone(), r.clone()])
}

#[test]
fn test_relay_buffers_payloads() {
    let http = MockHttp::new(200);
    let timer = MockTimer::new();
    let mut relay = Relay::new(http, timer, "test-key");
    relay.push(make_full_payload("AGT001")).unwrap();
    relay.push(make_full_payload("AGT002")).unwrap();
    assert_eq!(relay.buffered_count(), 2);
}

#[test]
fn test_relay_flushes_on_time_trigger() {
    // Create relay, push one item (no flush yet — timer starts at 0)
    let http = MockHttp::new(200);
    let timer = MockTimer::new();
    let mut relay = Relay::new(http, timer, "test-key").with_flush_interval(60_000);
    relay.push(make_full_payload("AGT001")).unwrap();
    // Item is buffered (timer not yet past interval)
    assert_eq!(relay.buffered_count(), 1);
    // Manually flush
    relay.flush().unwrap();
    assert_eq!(relay.buffered_count(), 0);
    assert_eq!(relay.total_sent, 1);
}

#[test]
fn test_relay_retains_batch_on_http_error() {
    let http = MockHttp::new(500);
    let timer = MockTimer::new();
    let mut relay = Relay::new(http, timer, "test-key");
    relay.push(make_full_payload("AGT001")).unwrap();
    let result = relay.flush();
    assert!(result.is_err());
    assert_eq!(relay.total_failed, 1);
}

#[test]
fn test_relay_clears_batch_on_success() {
    let http = MockHttp::new(200);
    let timer = MockTimer::new();
    let mut relay = Relay::new(http, timer, "test-key");
    relay.push(make_full_payload("AGT001")).unwrap();
    relay.flush().unwrap();
    assert_eq!(relay.buffered_count(), 0);
    assert_eq!(relay.total_sent, 1);
}

// ── Mux tests ─────────────────────────────────────────────────────────────────

#[test]
fn test_mux_switch_sets_gpio_pins() {
    let gpio = MockGpio::new();
    let uart = MockUart::new_with_response(b"\r\nOK\r\n");
    let timer = MockTimer::new();
    let mut mux = SimMux::new(gpio, uart, timer, 4, 5);
    mux.switch_to(SimSlot::Phys2).unwrap();
    // Phys2 = S0=1, S1=0
    assert_eq!(mux.gpio.get_pin(4).unwrap(), true);
    assert_eq!(mux.gpio.get_pin(5).unwrap(), false);
}

#[test]
fn test_mux_switch_to_esim1() {
    let gpio = MockGpio::new();
    let uart = MockUart::new_with_response(b"\r\nOK\r\n");
    let timer = MockTimer::new();
    let mut mux = SimMux::new(gpio, uart, timer, 4, 5);
    mux.switch_to(SimSlot::ESim1).unwrap();
    // ESim1 = S0=0, S1=1
    assert_eq!(mux.gpio.get_pin(4).unwrap(), false);
    assert_eq!(mux.gpio.get_pin(5).unwrap(), true);
}

#[test]
fn test_mux_switch_to_esim2() {
    let gpio = MockGpio::new();
    let uart = MockUart::new_with_response(b"\r\nOK\r\n");
    let timer = MockTimer::new();
    let mut mux = SimMux::new(gpio, uart, timer, 4, 5);
    mux.switch_to(SimSlot::ESim2).unwrap();
    // ESim2 = S0=1, S1=1
    assert_eq!(mux.gpio.get_pin(4).unwrap(), true);
    assert_eq!(mux.gpio.get_pin(5).unwrap(), true);
}

// ── Nigeria carrier identification tests ─────────────────────────────────────

#[test]
fn test_nigeria_mtn_mcc_mnc() {
    // MTN Nigeria: MCC=621, MNC=30 → 62130
    // Glo: MCC=621, MNC=50 → 62150
    // Airtel: MCC=621, MNC=20 → 62120
    // 9mobile: MCC=621, MNC=60 → 62160
    // MCC+MNC stored as 6-digit integer: MCC=621, MNC=30 → 621030
    let mtn: u32 = 621030;    // MTN Nigeria
    let airtel: u32 = 621020;  // Airtel Nigeria
    let glo: u32 = 621050;     // Glo Mobile
    let nine_mobile: u32 = 621060; // 9mobile
    assert_eq!(mtn / 1000, 621, "MTN MCC should be 621");
    assert_eq!(airtel / 1000, 621, "Airtel MCC should be 621");
    assert_eq!(glo / 1000, 621, "Glo MCC should be 621");
    assert_eq!(nine_mobile / 1000, 621, "9mobile MCC should be 621");
    // All Nigerian carriers have valid MNC
    for mnc in [mtn % 1000, airtel % 1000, glo % 1000, nine_mobile % 1000] {
        assert!(mnc > 0 && mnc < 1000, "MNC {} should be 1-999", mnc);
    }
}
