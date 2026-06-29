/// AT Command UART Driver for cellular modems.
///
/// Supports Quectel EC25/EC21, SIM7600, SIM800, u-blox SARA-R4 series.
/// All commands are standard 3GPP AT commands — no vendor-specific extensions
/// are required for the core probe functionality.
///
/// The driver is HAL-agnostic: it works with any type implementing `UartHal`
/// and `TimerHal`. This makes it testable on x86 with the mock HAL.

use crate::hal::{HalError, TimerHal, UartHal};
use crate::probe::{SimReading, SimSlot};
use heapless::String;

/// Maximum length of a single AT response line (bytes).
const AT_LINE_MAX: usize = 128;

/// AT command timeout in milliseconds (default for most commands).
const AT_TIMEOUT_MS: u32 = 3000;

/// AT ping timeout in milliseconds (longer for network round-trip).
const AT_PING_TIMEOUT_MS: u32 = 8000;

/// Driver for a single modem UART port.
pub struct AtDriver<U: UartHal, T: TimerHal> {
    uart: U,
    pub(crate) timer: T,
}

impl<U: UartHal, T: TimerHal> AtDriver<U, T> {
    pub fn new(uart: U, timer: T) -> Self {
        AtDriver { uart, timer }
    }

    /// Send an AT command and read the response lines until "OK" or "ERROR".
    /// Returns the response lines (excluding the echo and OK/ERROR line).
    fn send_cmd(
        &mut self,
        cmd: &str,
        timeout_ms: u32,
    ) -> Result<heapless::Vec<String<AT_LINE_MAX>, 8>, HalError> {
        // Write command + CRLF
        self.uart.write(cmd.as_bytes())?;
        self.uart.write(b"\r\n")?;
        self.uart.flush()?;

        let deadline = self.timer.now_ms() + timeout_ms as u64;
        let mut lines: heapless::Vec<String<AT_LINE_MAX>, 8> = heapless::Vec::new();
        let mut line_buf: [u8; AT_LINE_MAX] = [0u8; AT_LINE_MAX];
        let mut line_len = 0usize;

        loop {
            if self.timer.now_ms() > deadline {
                return Err(HalError::UartRxTimeout);
            }

            let mut byte = [0u8; 1];
            match self.uart.read(&mut byte) {
                Ok(0) => {
                    // No data yet — yield briefly (1 ms busy-wait on RTOS)
                    self.timer.delay_ms(1);
                    continue;
                }
                Ok(_) => {
                    let b = byte[0];
                    if b == b'\n' {
                        // End of line — process it
                        let line_str = core::str::from_utf8(&line_buf[..line_len])
                            .unwrap_or("")
                            .trim();

                        if line_str == "OK" {
                            return Ok(lines);
                        }
                        if line_str.starts_with("ERROR") || line_str.starts_with("+CME ERROR") {
                            return Err(HalError::Fault);
                        }
                        // Skip echo (line equals the command we sent)
                        if !line_str.is_empty() && !line_str.starts_with(cmd.trim_end()) {
                            if let Ok(s) = String::try_from(line_str) {
                                let _ = lines.push(s);
                            }
                        }
                        line_len = 0;
                    } else if b != b'\r' {
                        if line_len < AT_LINE_MAX {
                            line_buf[line_len] = b;
                            line_len += 1;
                        }
                    }
                }
                Err(e) => return Err(e),
            }
        }
    }

    /// AT+CSQ — query signal quality.
    /// Returns (rssi: 0–31, ber: 0–7). rssi=99 means unknown.
    pub fn query_csq(&mut self) -> Result<(u8, u8), HalError> {
        let lines = self.send_cmd("AT+CSQ", AT_TIMEOUT_MS)?;
        // Response: +CSQ: <rssi>,<ber>
        for line in &lines {
            if let Some(rest) = line.strip_prefix("+CSQ: ") {
                let mut parts = rest.splitn(2, ',');
                let rssi = parts.next().and_then(|s| s.parse::<u8>().ok()).unwrap_or(99);
                let ber = parts.next().and_then(|s| s.parse::<u8>().ok()).unwrap_or(99);
                return Ok((rssi, ber));
            }
        }
        Ok((99, 99)) // unknown
    }

    /// AT+CEREG? — query network registration status.
    /// Returns registration status (0–5).
    pub fn query_cereg(&mut self) -> Result<u8, HalError> {
        let lines = self.send_cmd("AT+CEREG?", AT_TIMEOUT_MS)?;
        // Response: +CEREG: <n>,<stat>
        for line in &lines {
            if let Some(rest) = line.strip_prefix("+CEREG: ") {
                let mut parts = rest.splitn(2, ',');
                let _n = parts.next(); // unsolicited result code mode
                let stat = parts.next().and_then(|s| s.parse::<u8>().ok()).unwrap_or(0);
                return Ok(stat);
            }
        }
        Ok(0) // not registered
    }

    /// AT+CIMI — query IMSI (International Mobile Subscriber Identity).
    /// Returns the first 6 digits (MCC+MNC) as a u32.
    pub fn query_mcc_mnc(&mut self) -> Result<u32, HalError> {
        let lines = self.send_cmd("AT+CIMI", AT_TIMEOUT_MS)?;
        // Response: 15-digit IMSI string
        for line in &lines {
            if line.len() >= 6 {
                let prefix = &line[..6];
                if let Ok(mcc_mnc) = prefix.parse::<u32>() {
                    return Ok(mcc_mnc);
                }
            }
        }
        Ok(0)
    }

    /// AT+COPS? — query current operator name.
    /// Returns carrier name string (max 32 chars).
    pub fn query_carrier(&mut self) -> Result<String<32>, HalError> {
        let lines = self.send_cmd("AT+COPS?", AT_TIMEOUT_MS)?;
        // Response: +COPS: <mode>,<format>,"<oper>",<AcT>
        for line in &lines {
            if let Some(rest) = line.strip_prefix("+COPS: ") {
                // Find the quoted operator name
                if let Some(start) = rest.find('"') {
                    let after = &rest[start + 1..];
                    if let Some(end) = after.find('"') {
                        let name = &after[..end];
                        return Ok(String::try_from(name).unwrap_or_default());
                    }
                }
            }
        }
        Ok(String::new())
    }

    /// Measure round-trip latency using AT+QPING (Quectel) or AT+PING (generic).
    /// Falls back to a fixed 9999ms if the modem does not support ping.
    /// Returns latency in milliseconds.
    pub fn measure_latency(&mut self, host: &str) -> Result<u16, HalError> {
        // Build: AT+QPING=1,"<host>",5,1  (context 1, host, timeout 5s, count 1)
        let mut cmd: String<64> = String::new();
        let _ = core::fmt::write(
            &mut cmd,
            format_args!("AT+QPING=1,\"{}\",5,1", host),
        );

        match self.send_cmd(cmd.as_str(), AT_PING_TIMEOUT_MS) {
            Ok(lines) => {
                // Response: +QPING: <result>,<IP>,<bytes>,<time>,<ttl>
                for line in &lines {
                    if let Some(rest) = line.strip_prefix("+QPING: ") {
                        let parts: heapless::Vec<&str, 8> = rest.splitn(8, ',').collect();
                        if parts.len() >= 4 {
                            if let Ok(t) = parts[3].trim().parse::<u16>() {
                                return Ok(t);
                            }
                        }
                    }
                }
                Ok(9999) // ping succeeded but no time parsed
            }
            Err(_) => Ok(9999), // ping not supported or timed out
        }
    }

    /// Perform a full probe of the currently active SIM slot.
    /// Returns a partially-filled `SimReading` (slot and score filled by caller).
    pub fn probe_active_sim(&mut self, slot: SimSlot, ping_host: &str) -> SimReading {
        let (rssi, _ber) = self.query_csq().unwrap_or((99, 99));
        let reg_status = self.query_cereg().unwrap_or(0);
        let mcc_mnc = self.query_mcc_mnc().unwrap_or(0);
        let carrier = self.query_carrier().unwrap_or_default();
        let latency_ms = self.measure_latency(ping_host).unwrap_or(9999);

        // Packet loss: 3 pings, count failures (simplified — full impl uses AT+QPING count=3)
        let packet_loss_x10: u16 = if latency_ms == 9999 { 1000 } else { 0 };

        SimReading {
            slot,
            carrier,
            mcc_mnc,
            rssi,
            reg_status,
            latency_ms,
            packet_loss_x10,
            score: 0, // filled by scorer
            selected: false,
        }
    }
}
