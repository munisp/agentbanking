/// Hardware Abstraction Layer (HAL) traits for the SIM Orchestrator.
///
/// These traits are the ONLY interface between the orchestrator logic and the
/// underlying hardware. Swapping the HAL implementation (mock, STM32, Android NDK)
/// changes the compile target without touching any orchestrator logic.
///
/// All methods are synchronous and infallible at the type level — errors are
/// returned as `Result<_, HalError>` to allow graceful degradation.

/// Error type for HAL operations — kept small for no_std compatibility.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HalError {
    /// UART transmit buffer full or line not ready.
    UartTxFull,
    /// UART receive timeout — no bytes within the deadline.
    UartRxTimeout,
    /// UART framing or parity error.
    UartFraming,
    /// GPIO pin direction mismatch or pin not configured.
    GpioConfig,
    /// Timer not started or already expired.
    TimerExpired,
    /// HTTP layer not available (no bearer context active).
    HttpUnavailable,
    /// HTTP request failed (non-2xx or network error).
    HttpError(u16),
    /// Generic hardware fault.
    Fault,
}

impl core::fmt::Display for HalError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            HalError::UartTxFull => write!(f, "UART TX buffer full"),
            HalError::UartRxTimeout => write!(f, "UART RX timeout"),
            HalError::UartFraming => write!(f, "UART framing error"),
            HalError::GpioConfig => write!(f, "GPIO config error"),
            HalError::TimerExpired => write!(f, "Timer expired"),
            HalError::HttpUnavailable => write!(f, "HTTP unavailable"),
            HalError::HttpError(code) => write!(f, "HTTP error {}", code),
            HalError::Fault => write!(f, "Hardware fault"),
        }
    }
}

/// UART HAL — used to send AT commands to the modem and read responses.
///
/// Implementations must be byte-oriented and non-blocking at the HAL level.
/// The orchestrator drives the read loop with a timeout via `TimerHal`.
pub trait UartHal {
    /// Write a byte slice to the UART TX buffer.
    /// Returns `HalError::UartTxFull` if the buffer cannot accept all bytes.
    fn write(&mut self, data: &[u8]) -> Result<(), HalError>;

    /// Read up to `buf.len()` bytes from the UART RX buffer.
    /// Returns the number of bytes actually read (0 if no data available).
    fn read(&mut self, buf: &mut [u8]) -> Result<usize, HalError>;

    /// Flush the TX buffer (block until all bytes are transmitted).
    fn flush(&mut self) -> Result<(), HalError>;
}

/// GPIO HAL — used to control the SIM multiplexer select lines.
///
/// The SIM mux (e.g. TS3A27518E) has 2 select lines (S0, S1) that choose
/// which of the 4 SIM slots is routed to the modem:
///   S1=0, S0=0 → SIM 1 (Physical)
///   S1=0, S0=1 → SIM 2 (Physical)
///   S1=1, S0=0 → eSIM 1
///   S1=1, S0=1 → eSIM 2
pub trait GpioHal {
    /// Set the logical level of a GPIO pin (true = high, false = low).
    fn set_pin(&mut self, pin: u8, high: bool) -> Result<(), HalError>;

    /// Read the logical level of a GPIO pin.
    fn get_pin(&self, pin: u8) -> Result<bool, HalError>;
}

/// Timer HAL — used for probe intervals and AT command timeouts.
pub trait TimerHal {
    /// Return the current monotonic timestamp in milliseconds.
    /// Must be monotonically increasing and not wrap for at least 24 hours.
    fn now_ms(&self) -> u64;

    /// Block (busy-wait or RTOS delay) for the given number of milliseconds.
    /// On FreeRTOS, this should call `vTaskDelay()`.
    /// On std, this should call `std::thread::sleep()`.
    fn delay_ms(&self, ms: u32);
}

/// HTTP HAL — used to POST probe payloads to the 54agent platform.
///
/// On FreeRTOS, this is implemented via AT+HTTPPARA / AT+HTTPACTION commands
/// sent through the modem UART. On std, this is a plain reqwest POST.
pub trait HttpHal {
    /// POST a JSON payload to the given URL.
    /// Returns the HTTP status code on success, or `HalError::HttpError(code)`.
    /// The body is a UTF-8 JSON string (max 2048 bytes for no_std targets).
    fn post_json(&mut self, url: &str, body: &str) -> Result<u16, HalError>;
}

/// WiFi HAL — used to probe the WiFi interface for connectivity metrics.
///
/// On Android/Linux, this reads from the WifiManager / nl80211 netlink socket.
/// On FreeRTOS, this reads from the ESP-IDF WiFi driver or LwIP.
/// On targets without WiFi, implement all methods to return `HalError::Fault`.
pub trait WifiHal {
    /// Return true if a WiFi interface is present and associated to an AP.
    fn is_connected(&self) -> bool;

    /// Return the SSID of the connected AP (max 32 bytes).
    /// Returns `HalError::Fault` if not connected.
    fn ssid(&self) -> Result<heapless::String<32>, HalError>;

    /// Return the BSSID of the connected AP as a 6-byte array.
    /// Returns `HalError::Fault` if not connected.
    fn bssid(&self) -> Result<[u8; 6], HalError>;

    /// Return the RSSI in dBm (negative value, e.g. -65).
    /// Typical range: -30 (excellent) to -90 (unusable).
    /// Returns `HalError::Fault` if not connected.
    fn rssi_dbm(&self) -> Result<i16, HalError>;

    /// Return the channel number (1–14 for 2.4GHz, 36–165 for 5GHz).
    fn channel(&self) -> Result<u8, HalError>;

    /// Measure round-trip latency to the default gateway in milliseconds.
    /// Returns 0xFFFF if the ping fails.
    fn gateway_latency_ms(&mut self) -> u16;

    /// Return the IPv4 address of the WiFi interface as a u32 (big-endian).
    /// Returns 0 if not connected.
    fn ip_address(&self) -> u32;
}
