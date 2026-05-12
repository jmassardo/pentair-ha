# Plan: Native Home Assistant Integration for Pentair EasyTouch

## Repository
- **Location:** `~/code/pentair-ha/`
- **Target install path:** `custom_components/pentair_easytouch/` inside a Home Assistant instance
- **Reference codebase:** `~/code/nodejs-poolController/` (tagyoureit/nodejs-poolController)
  - Protocol spec lives in the TypeScript source, especially:
    - `controller/comms/Comms.ts` — RS485 transport
    - `controller/comms/messages/` — message handlers (27 files)
    - `controller/boards/EasyTouchBoard.ts` — EasyTouch board logic
    - `controller/boards/SystemBoard.ts` — base board + valueMaps
    - `controller/Equipment.ts` — equipment config model
    - `controller/State.ts` — runtime state model
  - Live equipment data for testing: `data/poolConfig.json`, `data/poolState.json`

## Problem Statement
Rewrite the RS485 protocol and equipment logic from nodejs-poolController (TypeScript/Node.js)
into a native Python Home Assistant custom integration (`custom_components/pentair_easytouch/`).
No separate containers, no MQTT middleman — runs directly inside HA.

## Scope
- **Controller:** EasyTouch (ET2-8, ET2-4, ET-PSL4, etc.) — single board target
- **Transport:** TCP-to-serial (RS485-Ethernet adapter via `asyncio` streams) and direct serial via `pyserial-asyncio`
- **Protocol:** Pentair RS485 broadcast protocol (preamble `[255,0,255,165,1,...]`)

## Architecture

```
custom_components/pentair_easytouch/
├── __init__.py              # Integration setup, config entry lifecycle
├── manifest.json            # Dependencies: pyserial-asyncio
├── config_flow.py           # UI setup: connection type, host/port or serial path
├── const.py                 # Domain, protocol constants, action codes
├── coordinator.py           # DataUpdateCoordinator — bridge between protocol and HA
│
├── protocol/                # Pure protocol layer (no HA dependency)
│   ├── __init__.py
│   ├── transport.py         # TCP + serial async transport abstraction
│   ├── framing.py           # Packet framing: preamble, header, checksum, parse/build
│   ├── messages.py          # Message router (action code → handler dispatch)
│   ├── status.py            # Action 2 decode: time, mode, temps, circuit states, delays
│   ├── pump.py              # Pump status/config decode (Intelliflo protocol)
│   ├── chlorinator.py       # IntelliChlor status/control decode
│   ├── commands.py          # Outbound command builders (set circuit, heat mode, theme, etc.)
│   └── valuemaps.py         # Enums/lookups: heat modes, circuit types, light themes, etc.
│
├── model.py                 # Equipment + State data model (dataclasses)
│
├── switch.py                # HA switch entities (circuits, features)
├── light.py                 # HA light entities (IntelliBrite w/ effects)
├── sensor.py                # HA sensor entities (temps, pump RPM/watts/flow, salt, etc.)
├── binary_sensor.py         # HA binary sensors (heater on, freeze protect, delays)
├── climate.py               # HA climate entities (pool/spa bodies w/ heat mode + setpoint)
├── number.py                # HA number entities (chlorinator setpoints, schedules)
├── select.py                # HA select entities (heat mode, valve mode)
└── diagnostics.py           # HA diagnostics dump for troubleshooting
```

## Phases

### Phase 1 — Protocol Foundation
Port the RS485 transport and packet framing. No HA dependency — pure Python, fully testable.

- **transport.py**: Async TCP client (connect, reconnect, read loop) + serial port abstraction
  - TCP: `asyncio.open_connection(host, port)` with auto-reconnect
  - Serial: `serial_asyncio.open_serial_connection()` at 9600/8N1
  - Callback-based: `on_data(bytes)` feeds framing layer
- **framing.py**: Packet parser state machine
  - Preamble detection: `[255, 0, 255]` then `[165, 1]`
  - Header: `[165, 1, DEST, SRC, ACTION, LEN]`
  - Payload: `LEN` bytes
  - Checksum: 2-byte sum of header+payload, big-endian
  - Builder: construct outbound packets with correct checksum
- **const.py**: Protocol constants
  - Addresses: broadcast=15, controller=16, njsPC=33 (configurable)
  - Action codes: 2 (status), 5 (datetime), 8 (heat status), 10 (custom names),
    11 (circuit names), 17 (schedules), 24 (pump status/control),
    25 (pump config), 27 (IntelliChlor), 30/228 (config), 96 (intellibrite),
    131 (cancel delay), 134 (circuit set), 136 (heat setpoint),
    138 (custom name set), 145 (schedule set), 153 (chlor set),
    167 (light group set), 168 (heat mode set), etc.

**Tests:** Unit tests with captured packet bytes from njsPC replay data.

### Phase 2 — Message Decoding (Status)
Decode the main EasyTouch status broadcasts.

- **status.py** — Action 2 decode (the big one, ~29-byte payload):
  - Byte 0: hour, Byte 1: minute
  - Byte 2: equipment status word (circuit bitmask bytes 2-3)
  - Bytes 4-5: mode flags (service, freeze, timeout)
  - Byte 9: heat status (pool heating, spa heating)
  - Byte 14: air temp, Byte 15: body temps
  - Bytes 6-7: delay flags
  - Circuit on/off bitmask: bytes 2-3 for circuits 1-8, byte 8 for features 1-8
  - Full field mapping from EquipmentStateMessage.ts action 2
- **pump.py** — Pump protocol decode:
  - Request/response on pump addresses (96-111)
  - Status fields: watts, RPM, flow, mode, driveState, status
- **chlorinator.py** — IntelliChlor decode:
  - Salt level, output %, super chlor, status codes, model

**Deliverable:** Given raw packets, produce a populated `PoolState` dataclass.

### Phase 3 — Data Model
Define the state and config model as Python dataclasses.

- **model.py**:
  ```python
  @dataclass
  class PoolBody:           # id, name, type, temp, setPoint, heatMode, heatStatus, isOn, coolSetpoint
  class Circuit:            # id, name, type, isOn, freezeProtect, showInFeatures, isLight, lightingTheme
  class Feature:            # id, name, type, isOn, freezeProtect, showInFeatures
  class Pump:               # id, name, type, isActive, rpm, watts, flow, status, mode, circuits[]
  class Valve:              # id, name, type, isDiverted
  class Heater:             # id, name, type, isOn, bodyId
  class Chlorinator:        # id, name, model, poolSetpoint, spaSetpoint, saltLevel, currentOutput, status, superChlor
  class Schedule:           # id, circuit, startTime, endTime, scheduleDays, scheduleType, isActive
  class TemperatureState:   # air, waterSensor1, waterSensor2, solar, units
  class EquipmentConfig:    # model, softwareVersion, maxCircuits, maxFeatures, maxPumps, etc.
  class PoolState:          # equipment, temps, bodies[], circuits[], features[], pumps[], valves[],
                            # heaters[], chlorinators[], schedules[], mode, status, time
  ```

### Phase 4 — Outbound Commands
Build and send control messages to the EasyTouch controller.

- **commands.py**:
  - `set_circuit_state(id, on/off)` → Action 134
  - `set_heat_mode(body_id, mode)` → Action 168
  - `set_heat_setpoint(body_id, temp)` → Action 136
  - `set_light_theme(circuit_id, theme)` → Action 96
  - `set_chlorinator(pool_pct, spa_pct)` → Action 153
  - `set_schedule(id, circuit, start, end, days)` → Action 145
  - `cancel_delay()` → Action 131
  - `set_pump_speed(pump_id, circuit_id, speed)` → via pump protocol
  - Each builds proper packet via framing.py and queues for send
  - Response matching / retry with timeout

### Phase 5 — HA Integration Glue
Wire protocol layer into Home Assistant's architecture.

- **config_flow.py**: UI setup wizard
  - Step 1: Connection type (TCP / Serial)
  - Step 2a: TCP → host + port (default 9801)
  - Step 2b: Serial → port path + baud rate
  - Validation: attempt connect, verify we see Action 2 broadcasts
- **coordinator.py**: `DataUpdateCoordinator` subclass
  - Owns the transport + framing + message pipeline
  - On each decoded status message → update `PoolState` → notify entities
  - Passive listener model (controller broadcasts status every ~1-2 sec)
  - No polling needed — RS485 is push-based
  - Handles reconnection, error recovery
- **__init__.py**: `async_setup_entry` / `async_unload_entry`
  - Creates coordinator, starts transport
  - Forwards entity platform setup

### Phase 6 — Entity Platforms
Map equipment state to HA entities.

#### switch.py — Circuits + Features
| Equipment | Entity | Controls |
|-----------|--------|----------|
| Generic circuit | `switch` | on/off via Action 134 |
| Feature | `switch` | on/off via Action 134 |

#### light.py — IntelliBrite
| Equipment | Entity | Controls |
|-----------|--------|----------|
| IntelliBrite circuit | `light` | on/off + effect_list (themes: party, romance, caribbean, etc.) |

#### climate.py — Pool/Spa Bodies
| Equipment | Entity | Controls |
|-----------|--------|----------|
| Pool body | `climate` | heat setpoint, heat mode (off/heater/solar/solarpref), current temp |
| Spa body | `climate` | same |

#### sensor.py — Read-Only Sensors
| Equipment | Entity | Unit |
|-----------|--------|------|
| Air temp | `sensor` | °F/°C |
| Water temp | `sensor` | °F/°C |
| Solar temp | `sensor` | °F/°C |
| Pump RPM | `sensor` | rpm |
| Pump watts | `sensor` | W |
| Pump flow | `sensor` | gpm |
| Salt level | `sensor` | ppm |
| Chlorinator output | `sensor` | % |
| System status | `sensor` | text |

#### binary_sensor.py — Boolean States
| Equipment | Entity |
|-----------|--------|
| Heater active | `binary_sensor` |
| Freeze protect active | `binary_sensor` |
| Delay active | `binary_sensor` |
| Pump running | `binary_sensor` |
| Valve diverted | `binary_sensor` |

#### number.py — Adjustable Values
| Equipment | Entity | Range |
|-----------|--------|-------|
| Chlorinator pool % | `number` | 0-100 |
| Chlorinator spa % | `number` | 0-100 |

#### select.py — Mode Selectors
| Equipment | Entity | Options |
|-----------|--------|---------|
| System mode | `select` | Auto / Service / Timeout |

### Phase 7 — Polish & Testing
- **diagnostics.py**: Dump full PoolState for support/debugging
- **strings.json** / **translations/**: Localization
- Integration tests with recorded packet captures
- HACS repository packaging (repo structure, hacs.json, info.md)
- README with setup instructions

## Key Design Decisions

1. **Pure protocol layer** — `protocol/` has zero HA imports. Can be tested independently,
   reused in CLI tools, or packaged separately.
2. **Passive listener** — EasyTouch broadcasts Action 2 every ~1s. We listen and decode,
   no polling. Commands are fire-and-send.
3. **No config persistence** — HA's config entries store connection params. Equipment
   discovery is automatic from protocol broadcasts.
4. **Entity registry** — Entities are created dynamically as equipment is discovered
   from status broadcasts (circuit bitmask tells us what's active).
5. **Coordinator pattern** — Single coordinator owns the connection. All entities
   subscribe to coordinator updates. Standard HA pattern.

## Estimated Effort by Phase

| Phase | Description | Est. Python LOC |
|-------|-------------|-----------------|
| 1 | Protocol foundation | ~600 |
| 2 | Message decoding | ~800 |
| 3 | Data model | ~300 |
| 4 | Outbound commands | ~500 |
| 5 | HA integration glue | ~400 |
| 6 | Entity platforms | ~1,200 |
| 7 | Polish & testing | ~1,000 |
| **Total** | | **~4,800** |

## Dependencies
- `pyserial-asyncio` — async serial port access
- No other external deps (HA provides everything else)

## Reference Material
- nodejs-poolController source (`~/code/nodejs-poolController/`): protocol encode/decode is the spec
- Captured packets in replay data for test fixtures
- EasyTouch board valueMaps in `SystemBoard.ts` + `EasyTouchBoard.ts`
