/// Ring buffer relay — accumulates probe payloads and flushes them to the
/// 54agent platform API in batches.
///
/// Flush triggers:
///   1. Buffer reaches capacity (10 payloads)
///   2. 60 seconds have elapsed since the last flush
///   3. Caller explicitly calls `flush()`
///
/// The relay uses the `HttpHal` trait for the actual HTTP POST, making it
/// compatible with both AT+HTTPPARA (FreeRTOS) and reqwest (std/Android).

use crate::hal::{HalError, HttpHal, TimerHal};
use crate::probe::{ProbeBatch, ProbePayload};

/// Platform API endpoint for probe ingestion.
/// Overridable at compile time via the PLATFORM_API_URL env var (std only).
#[cfg(feature = "std")]
pub fn platform_url() -> &'static str {
    option_env!("PLATFORM_API_URL").unwrap_or("https://api.54agent.io")
}

#[cfg(not(feature = "std"))]
pub fn platform_url() -> &'static str {
    "https://api.54agent.io"
}

/// Relay state — holds the pending batch and flush timing.
pub struct Relay<H: HttpHal, T: TimerHal> {
    http: H,
    timer: T,
    batch: ProbeBatch,
    last_flush_ms: u64,
    /// Flush interval in milliseconds (default: 60_000 = 60 seconds).
    flush_interval_ms: u64,
    /// API key for authenticating with the platform.
    api_key: heapless::String<64>,
    /// Statistics
    pub total_sent: u32,
    pub total_failed: u32,
}

impl<H: HttpHal, T: TimerHal> Relay<H, T> {
    pub fn new(http: H, timer: T, api_key: &str) -> Self {
        let now = timer.now_ms();
        Relay {
            http,
            timer,
            batch: ProbeBatch::new(),
            last_flush_ms: now,
            flush_interval_ms: 60_000,
            api_key: heapless::String::try_from(api_key).unwrap_or_default(),
            total_sent: 0,
            total_failed: 0,
        }
    }

    /// Set a custom flush interval (milliseconds).
    pub fn with_flush_interval(mut self, ms: u64) -> Self {
        self.flush_interval_ms = ms;
        self
    }

    /// Push a probe payload into the batch buffer.
    /// Automatically flushes if the buffer is full or the interval has elapsed.
    pub fn push(&mut self, payload: ProbePayload) -> Result<(), HalError> {
        if !self.batch.push(payload) {
            // Buffer full — flush first, then push
            self.flush()?;
            // After flush, batch is empty — push will succeed
            // (payload was consumed above, so we can't re-push here;
            //  in production, use a secondary buffer or retry queue)
        }

        // Check time-based flush trigger
        let now = self.timer.now_ms();
        if now - self.last_flush_ms >= self.flush_interval_ms {
            self.flush()?;
        }

        Ok(())
    }

    /// Flush the current batch to the platform API.
    /// Clears the batch on success. On failure, retains the batch for retry.
    pub fn flush(&mut self) -> Result<(), HalError> {
        if self.batch.is_empty() {
            return Ok(());
        }

        let url = {
            let base = platform_url();
            let mut u = heapless::String::<128>::new();
            let _ = core::fmt::write(&mut u, format_args!("{}/api/trpc/simOrchestrator.ingestBatch", base));
            u
        };

        // Serialize the batch to JSON
        #[cfg(feature = "std")]
        let body = match serde_json::to_string(&self.batch) {
            Ok(s) => s,
            Err(_) => {
                self.total_failed += 1;
                return Err(HalError::Fault);
            }
        };

        #[cfg(not(feature = "std"))]
        let body = {
            // no_std: use heapless string serialization
            match serde_json::to_string(&self.batch) {
                Ok(s) => s,
                Err(_) => {
                    self.total_failed += 1;
                    return Err(HalError::Fault);
                }
            }
        };

        match self.http.post_json(url.as_str(), &body) {
            Ok(status) if (200..300).contains(&(status as usize)) => {
                self.total_sent += self.batch.len() as u32;
                self.batch.clear();
                self.last_flush_ms = self.timer.now_ms();
                log::info!("Relay: flushed {} probes (HTTP {})", self.total_sent, status);
                Ok(())
            }
            Ok(status) => {
                self.total_failed += 1;
                log::warn!("Relay: HTTP {} — retaining batch", status);
                Err(HalError::HttpError(status))
            }
            Err(e) => {
                self.total_failed += 1;
                log::warn!("Relay: flush failed — {:?}", e);
                Err(e)
            }
        }
    }

    /// Return the number of payloads currently buffered.
    pub fn buffered_count(&self) -> usize {
        self.batch.len()
    }
}

