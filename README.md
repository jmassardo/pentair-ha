# Pentair EasyTouch for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-41BDF5.svg)](https://www.home-assistant.io/)

A native [Home Assistant](https://www.home-assistant.io/) integration for **Pentair EasyTouch** pool and spa controllers. Communicates directly over the RS-485 bus — no cloud, no internet dependency, no polling.

---

## Features

- **Real-time push updates** — passively listens to the RS-485 broadcast bus; entities update within seconds of a state change.
- **Full equipment control** — toggle circuits, set heat modes and setpoints, adjust chlorinator output, command IntelliBrite light shows, and more.
- **Zero cloud dependency** — runs entirely on your local network using a simple RS-485 adapter.

---

## Supported Equipment

| Equipment | Models | Notes |
|-----------|--------|-------|
| **Controller** | EasyTouch 4, EasyTouch 8, EasyTouch PL4, EasyTouch PSL4 | Main automation controller |
| **Pumps** | Pentair IntelliFlo VS, VF, VSF | RPM, watts, flow, and run status |
| **Chlorinator** | Pentair IntelliChlor IC20, IC40, IC60 | Salt level, output %, super-chlorinate |
| **Lights** | Pentair IntelliBrite | Color modes, on/off control |
| **Heaters** | Gas, solar, heat pump | Mode selection, setpoint control |
| **Valves** | Standard intake/return valves | Diverter status |

---

## Requirements

| Requirement | Details |
|-------------|---------|
| **Home Assistant** | 2024.1 or newer |
| **RS-485 adapter** | An RS-485 to TCP/Ethernet adapter (e.g., USR-TCP232, Elfin-EW, or any serial server) **or** a direct USB RS-485 adapter connected to the HA host |
| **Wiring** | Two-wire (A/B) connection to the EasyTouch RS-485 bus |
| **Python** | 3.12+ (ships with HA) |

> **Tip:** A TCP/Ethernet adapter is strongly recommended. It can be placed near the pool equipment panel and communicates over your existing network — no need to run a USB cable.

---

## Installation

### HACS (Recommended)

1. Open **HACS** → **Integrations** → **⋮** (three dots menu) → **Custom repositories**.
2. Enter the repository URL and select **Integration** as the category.
3. Click **Add**, then find **Pentair EasyTouch** in the HACS store.
4. Click **Download**, then restart Home Assistant.

### Manual

1. Copy the `custom_components/pentair_easytouch/` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Pentair EasyTouch**.
3. Select your connection type:
   - **TCP / Ethernet** — Enter the IP address and port of your RS-485 adapter (default port: `9801`).
   - **Serial / RS-485** — Enter the serial device path (e.g., `/dev/ttyUSB0`) and baud rate (default: `9600`).
4. Click **Submit**. The integration will verify the connection and begin discovering equipment.

> **Note:** Entities appear automatically as the controller broadcasts status messages. It may take up to 30 seconds for all entities to populate after the first connection.

---

## Entities

The integration automatically creates entities based on discovered equipment:

| Platform | Entity | Description |
|----------|--------|-------------|
| **Switch** | `switch.pool_circuit_*` | Toggle pool/spa circuits and features (pumps, waterfalls, spillovers, etc.) |
| **Light** | `light.pool_light_*` | IntelliBrite lights with color mode support |
| **Climate** | `climate.pool_body_*` | Pool and spa body heat control with mode and setpoint |
| **Sensor** | `sensor.pool_air_temp` | Air temperature reading |
| | `sensor.pool_water_temp_*` | Water temperature sensors |
| | `sensor.pool_pump_*_rpm` | Pump speed in RPM |
| | `sensor.pool_pump_*_watts` | Pump power consumption |
| | `sensor.pool_pump_*_flow` | Pump flow rate (GPM) |
| | `sensor.pool_salt_level` | IntelliChlor salt level (PPM) |
| | `sensor.pool_chlorinator_output` | Chlorinator current output % |
| **Binary Sensor** | `binary_sensor.pool_freeze_protect` | Freeze protection active |
| | `binary_sensor.pool_pump_*_running` | Pump running status |
| | `binary_sensor.pool_chlorinator_active` | Chlorinator active status |
| **Number** | `number.pool_chlorinator_pool_setpoint` | Chlorinator pool output setpoint (0–100%) |
| | `number.pool_chlorinator_spa_setpoint` | Chlorinator spa output setpoint (0–100%) |
| **Select** | `select.pool_*_heat_mode` | Heat mode selector (Off / Heater / Solar Preferred / Solar Only) |

---

## Supported Commands

| Action | Details |
|--------|---------|
| **Circuit control** | Turn any circuit or feature on/off |
| **Heat mode** | Set body heat mode (off, heater, solar preferred, solar only) |
| **Heat setpoint** | Adjust pool/spa target temperature |
| **Chlorinator output** | Set pool and spa chlorinator output percentage |
| **Light themes** | Command IntelliBrite color modes (party, romance, Caribbean, etc.) |
| **Super chlorinate** | Enable/disable super chlorination mode |

---

## How It Works

```
┌──────────────┐     RS-485      ┌──────────────┐     TCP/Serial    ┌──────────────┐
│  EasyTouch    │◄──────────────►│  RS-485       │◄─────────────────►│  Home         │
│  Controller   │   2-wire bus   │  Adapter      │   network/USB    │  Assistant    │
└──────────────┘                └──────────────┘                    └──────────────┘
```

1. **Passive listener** — The integration connects to the RS-485 bus via your adapter and listens to broadcast traffic. The EasyTouch controller broadcasts full equipment status every 1–2 seconds.
2. **Push model** — State updates are pushed to HA entities as soon as they are decoded. There is no polling interval.
3. **Command injection** — When you toggle a switch or change a setpoint, the integration injects a properly framed RS-485 command packet onto the bus. The controller processes it and confirms via the next status broadcast.
4. **Protocol pipeline** — Raw bytes flow through: `Transport → Framer → Router → PoolState → Coordinator → Entities`.

---

## Troubleshooting

| Symptom | Possible Cause | Solution |
|---------|---------------|----------|
| **Connection refused** | Adapter not powered or wrong IP/port | Verify the adapter is online and the IP/port match its configuration |
| **No entities appear** | Integration connected but no RS-485 traffic | Check RS-485 wiring (A/B polarity), ensure the controller is powered on |
| **Entities show "Unknown"** | Waiting for first status broadcast | Wait 30 seconds; the controller broadcasts periodically |
| **Stale values** | Transport disconnected silently | Check HA logs for reconnection messages; restart the integration |
| **Partial entities** | Some equipment not yet broadcast | Toggle equipment from the panel to trigger a broadcast, or wait for the next cycle |
| **Cannot control equipment** | Wiring is receive-only | Ensure your RS-485 adapter supports both TX and RX, and wiring includes both A and B lines |

### Viewing Diagnostics

1. Go to **Settings** → **Devices & Services** → **Pentair EasyTouch**.
2. Click the three-dot menu → **Download diagnostics**.
3. The downloaded JSON contains the full pool state (with connection details redacted).

### Debug Logging

Add the following to your `configuration.yaml` to enable verbose logging:

```yaml
logger:
  logs:
    custom_components.pentair_easytouch: debug
```

---

## Contributing

### Development Setup

```bash
# Clone the repository
git clone https://github.com/<your-org>/pentair-ha.git
cd pentair-ha

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the test suite
pytest

# Run linting and type checks
ruff check .
ruff format --check .
mypy .
```

### Project Structure

```
pentair-ha/
├── custom_components/
│   └── pentair_easytouch/
│       ├── protocol/          # RS-485 protocol layer (transport, framing, routing, commands)
│       ├── __init__.py        # HA integration setup
│       ├── config_flow.py     # UI-based configuration
│       ├── coordinator.py     # DataUpdateCoordinator (push model)
│       ├── model.py           # PoolState dataclass tree
│       ├── diagnostics.py     # Diagnostics dump for troubleshooting
│       ├── climate.py         # Pool/spa body climate entities
│       ├── switch.py          # Circuit/feature switch entities
│       ├── light.py           # IntelliBrite light entities
│       ├── sensor.py          # Temperature, pump, chlorinator sensors
│       ├── binary_sensor.py   # Freeze protect, pump status sensors
│       ├── number.py          # Chlorinator setpoint entities
│       └── select.py          # Heat mode selector entities
├── tests/                     # Test suite
├── hacs.json                  # HACS integration metadata
└── pyproject.toml             # Project configuration
```

---

## Credits

- Protocol documentation and message decoding inspired by the excellent [nodejs-poolController](https://github.com/tagyoureit/nodejs-poolController) project.
- Built for the Home Assistant community.

---

## License

This project is currently private and unlicensed. All rights reserved.
