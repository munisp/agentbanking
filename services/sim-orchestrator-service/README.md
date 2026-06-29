# 54agent SIM Orchestrator

Intelligent network selection daemon for 54agent POS terminals with multiple SIM cards.

## Overview

The SIM Orchestrator is a lightweight background process that continuously probes all available SIM interfaces (physical + eSIM) and automatically routes each POS transaction through the best available network. It is designed to run on:

- **Linux / Android** (PAX A920, Sunmi P2, Telpo TPS900) — full `std` runtime with Tokio
- **FreeRTOS / ThreadX / Zephyr** (bare-metal ARM Cortex-M/A) — `no_std` with HAL abstraction

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    POS Terminal Hardware                         │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  SIM 1   │  │  SIM 2   │  │  eSIM 1  │  │  eSIM 2  │       │
│  │  (MTN)   │  │ (Airtel) │  │  (Glo)   │  │ (9mobile)│       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       └─────────────┴─────────────┴──────────────┘             │
│                           │                                     │
│                    ┌──────┴──────┐                              │
│                    │  SIM Mux    │  GPIO S0/S1 select lines     │
│                    │ TS3A27518E  │                              │
│                    └──────┬──────┘                              │
│                           │                                     │
│                    ┌──────┴──────┐                              │
│                    │   Modem     │  Quectel EC25 / SIM7600      │
│                    │   (UART)    │  AT commands                 │
│                    └──────┬──────┘                              │
│                           │                                     │
│              ┌────────────┴────────────────┐                    │
│              │    SIM Orchestrator Daemon   │                    │
│              │                             │                    │
│              │  ┌─────────┐  ┌──────────┐  │                    │
│              │  │ Prober  │  │  Scorer  │  │                    │
│              │  │ AT+CSQ  │  │ RSSI 40% │  │                    │
│              │  │ AT+CEREG│  │  Lat 35% │  │                    │
│              │  │ AT+PING │  │ Loss 15% │  │                    │
│              │  └────┬────┘  │  Reg 10% │  │                    │
│              │       │       └────┬─────┘  │                    │
│              │       └────────────┘        │                    │
│              │              │              │                    │
│              │       ┌──────┴──────┐       │                    │
│              │       │   Relay     │       │                    │
│              │       │ Ring Buffer │       │                    │
│              │       │ 60s / 10 px │       │                    │
│              │       └──────┬──────┘       │                    │
│              └──────────────┼──────────────┘                    │
└─────────────────────────────┼───────────────────────────────────┘
                              │ HTTPS POST
                              ▼
                    ┌─────────────────┐
                    │  54agent Platform │
                    │  /api/trpc/      │
                    │  simOrchestrator │
                    │  .ingestProbe    │
                    └─────────────────┘
```

## SIM Scoring Algorithm

Each SIM interface is scored out of 1000 points using integer arithmetic (no FPU required):

| Metric | Weight | Measurement |
|---|---|---|
| Signal strength (RSSI) | 400 pts | AT+CSQ (0–31) |
| Latency | 350 pts | AT+QPING round-trip |
| Packet loss | 150 pts | 3-packet probe |
| Registration status | 100 pts | AT+CEREG (home=100, roaming=70) |

A SIM that is not registered scores 0 regardless of other metrics.

## Supported Modems

| Modem | AT Ping Command | Notes |
|---|---|---|
| Quectel EC25/EC21 | AT+QPING | Primary target |
| Quectel EC200U | AT+QPING | |
| SIM7600 / SIM7500 | AT+CIPPING | Fallback |
| SIM800 / SIM900 | AT+CIPPING | 2G only |
| u-blox SARA-R4 | AT+UPING | NB-IoT |

## Nigeria Carrier Configuration

| Slot | Carrier | MCC+MNC | Type |
|---|---|---|---|
| PHYS1 | MTN Nigeria | 62150 | Physical SIM |
| PHYS2 | Airtel Nigeria | 62120 | Physical SIM |
| ESIM1 | Glo Mobile | 62150 | eSIM |
| ESIM2 | 9mobile | 62160 | eSIM |

## Building

```bash
# Development / Linux (simulation mode — no real hardware needed)
source "$HOME/.cargo/env"
cd pos-sim-orchestrator
cargo build --release

# Run in simulation mode
SIM_AGENT_CODE=AGT001 SIM_TERMINAL_ID=TERM001 \
PLATFORM_API_URL=https://api.54agent.io \
SIM_API_KEY=your-key \
cargo run --release

# Run tests
cargo test

# Cross-compile for ARM Linux (PAX A920 / Android)
# rustup target add armv7-unknown-linux-gnueabihf
# cargo build --release --target armv7-unknown-linux-gnueabihf
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SIM_AGENT_CODE` | `AGT001` | Agent code of this terminal |
| `SIM_TERMINAL_ID` | `TERM-54agent-001` | Terminal serial number |
| `PLATFORM_API_URL` | `https://api.54agent.io` | 54agent platform API base URL |
| `SIM_API_KEY` | `dev-key-54agent` | API authentication key |
| `SIM_PROBE_INTERVAL_SECS` | `30` | How often to probe all SIMs |
| `SIM_RELAY_FLUSH_SECS` | `60` | How often to flush the relay buffer |
| `SIM_PING_HOST` | `8.8.8.8` | Host to ping for latency measurement |
| `SIM_UART_PORT` | _(empty)_ | Serial port (empty = simulation mode) |

## Health Endpoint

The daemon exposes a minimal HTTP health check on port 9200:

```
GET http://localhost:9200/health
→ {"status":"ok","agent":"AGT001","fw":"1.0.0"}
```

## FreeRTOS Integration

For bare-metal targets, the orchestrator is compiled as a static library with `no_std`. The RTOS task entry point calls `sim_orchestrator_task()` from C:

```c
// In your FreeRTOS task creation:
xTaskCreate(sim_orchestrator_task, "SIM_ORCH", 4096, NULL, tskIDLE_PRIORITY + 2, NULL);
```

The HAL implementations for your specific MCU are provided in the `sim-hal-stm32/` crate (not included — implement `UartHal`, `GpioHal`, `TimerHal`, `HttpHal` for your BSP).

## License

MIT — Copyright 2026 54agent Engineering
