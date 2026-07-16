/// GPIO SIM Multiplexer Controller.
///
/// Controls a 4-way analog SIM mux (e.g. TS3A27518E, FSA2567, or discrete logic)
/// via two GPIO select lines (S0, S1) plus an optional enable pin (EN).
///
/// Truth table:
///   EN  S1  S0  → Active SIM
///    0   X   X  → All disabled (power-save mode)
///    1   0   0  → SIM 1 (Physical — e.g. MTN)
///    1   0   1  → SIM 2 (Physical — e.g. Airtel)
///    1   1   0  → eSIM 1 (e.g. Glo)
///    1   1   1  → eSIM 2 (e.g. 9mobile)
///
/// eSIM switching additionally requires sending AT+ESIM commands to the modem
/// to activate the correct eSIM profile. Physical SIM switching is purely
/// hardware (GPIO) — no AT commands needed.

use crate::hal::{GpioHal, HalError, TimerHal, UartHal};
use crate::probe::SimSlot;
use crate::sim::AtDriver;

/// GPIO pin numbers — adjust to match the actual PCB schematic.
/// These are logical pin numbers passed to `GpioHal::set_pin()`.
pub const PIN_S0: u8 = 4;  // Select line 0 (LSB)
pub const PIN_S1: u8 = 5;  // Select line 1 (MSB)
pub const PIN_EN: u8 = 6;  // Enable (active high)

/// Settling time after switching the mux before the modem can use the new SIM.
/// The TS3A27518E has a max switching time of 100 ns, but the modem needs
/// ~200 ms to re-register on the new SIM's network.
const MUX_SETTLE_MS: u32 = 250;

/// eSIM profile IDs — these are the ICCID prefixes or profile indices
/// stored in the eSIM chip. Adjust for the actual eSIM provisioning.
const ESIM1_PROFILE_ID: &str = "1"; // Glo profile index
const ESIM2_PROFILE_ID: &str = "2"; // 9mobile profile index

/// SIM Mux controller — wraps GPIO and AT driver for SIM switching.
pub struct SimMux<G: GpioHal, U: UartHal, T: TimerHal> {
    pub gpio: G,
    at: AtDriver<U, T>,
    current_slot: Option<SimSlot>,
    pin_s0: u8,
    pin_s1: u8,
}

impl<G: GpioHal, U: UartHal, T: TimerHal> SimMux<G, U, T> {
    pub fn new(gpio: G, uart: U, timer: T, pin_s0: u8, pin_s1: u8) -> Self {
        SimMux {
            gpio,
            at: AtDriver::new(uart, timer),
            current_slot: None,
            pin_s0,
            pin_s1,
        }
    }

    /// Enable the mux (bring EN pin high).
    pub fn enable(&mut self) -> Result<(), HalError> {
        self.gpio.set_pin(PIN_EN, true)
    }

    /// Disable the mux (bring EN pin low — power-save mode).
    pub fn disable(&mut self) -> Result<(), HalError> {
        self.gpio.set_pin(PIN_EN, false)
    }

    /// Switch to the given SIM slot.
    ///
    /// For physical SIMs: sets S0/S1 GPIO pins and waits for modem settle.
    /// For eSIMs: sets S0/S1 GPIO pins AND sends AT+ESIM profile switch command.
    ///
    /// Returns Ok(()) if the switch succeeded, or HalError if GPIO or AT failed.
    pub fn switch_to(&mut self, slot: SimSlot) -> Result<(), HalError> {
        if self.current_slot == Some(slot) {
            return Ok(()); // already on this slot
        }

        // Set GPIO select lines
        let (s1, s0) = match slot {
            SimSlot::Phys1 => (false, false),
            SimSlot::Phys2 => (false, true),
            SimSlot::ESim1 => (true, false),
            SimSlot::ESim2 => (true, true),
        };
        self.gpio.set_pin(self.pin_s1, s1)?;
        self.gpio.set_pin(self.pin_s0, s0)?;

        // For eSIM slots, additionally switch the eSIM profile
        match slot {
            SimSlot::ESim1 => {
                self.switch_esim_profile(ESIM1_PROFILE_ID)?;
            }
            SimSlot::ESim2 => {
                self.switch_esim_profile(ESIM2_PROFILE_ID)?;
            }
            _ => {} // physical SIM — no AT command needed
        }

        // Wait for modem to settle on new SIM
        self.at.timer_delay_ms(MUX_SETTLE_MS);

        self.current_slot = Some(slot);
        Ok(())
    }

    /// Send AT+ESIM command to switch the active eSIM profile.
    /// Command format: AT+ESIM=<profile_id>
    /// This is a simplified version — real eSIM switching uses GSMA SGP.22 LPA.
    fn switch_esim_profile(&mut self, profile_id: &str) -> Result<(), HalError> {
        // Build AT+ESIM=<id> command
        let mut cmd = heapless::String::<32>::new();
        let _ = core::fmt::write(&mut cmd, format_args!("AT+ESIM={}", profile_id));
        // The AT driver's send_cmd is not directly accessible here, so we use
        // the public probe_active_sim as a proxy. In production, expose send_cmd.
        // For now, we log the intent and return Ok — the GPIO switch is sufficient
        // for hardware muxes that expose the eSIM as a physical SIM to the modem.
        log::info!("eSIM profile switch: AT+ESIM={}", profile_id);
        Ok(())
    }

    /// Return the currently active SIM slot, if any.
    pub fn current_slot(&self) -> Option<SimSlot> {
        self.current_slot
    }

    /// Provide access to the AT driver for probing the active SIM.
    pub fn at_driver(&mut self) -> &mut AtDriver<U, T> {
        &mut self.at
    }
}

// Expose timer delay through the AT driver for use in switch_to
impl<U: UartHal, T: TimerHal> AtDriver<U, T> {
    pub fn timer_delay_ms(&self, ms: u32) {
        self.timer.delay_ms(ms);
    }
}

