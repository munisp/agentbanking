/// 54agent SIM Orchestrator Library
///
/// This crate provides the core orchestrator logic for intelligent SIM selection
/// on 54agent POS terminals. It is HAL-agnostic and works with any implementation
/// of the HAL traits defined in `hal.rs`.
///
/// # Crate structure
/// - `hal`: Hardware Abstraction Layer traits (UartHal, GpioHal, TimerHal, HttpHal)
/// - `probe`: Probe payload types (SimReading, ProbePayload, ProbeBatch)
/// - `sim`: AT command UART driver
/// - `scorer`: Fixed-point signal scoring algorithm
/// - `mux`: GPIO SIM multiplexer controller
/// - `relay`: Ring buffer relay for batched HTTP upload

pub mod conn;
pub mod hal;
pub mod mux;
pub mod probe;
pub mod relay;
pub mod scorer;
pub mod sim;
pub mod watchdog;
pub mod wifi;
