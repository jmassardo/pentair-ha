# Pentair EasyTouch

Native Home Assistant integration for **Pentair EasyTouch** pool and spa controllers. Communicates directly over the RS-485 bus — no cloud, no internet, no polling.

## Supported Equipment

- **Controllers:** EasyTouch 4, EasyTouch 8, EasyTouch PL4, EasyTouch PSL4
- **Pumps:** Pentair IntelliFlo VS, VF, VSF
- **Chlorinator:** Pentair IntelliChlor IC20, IC40, IC60
- **Lights:** Pentair IntelliBrite (color modes)
- **Heaters:** Gas, solar, heat pump

## Requirements

- Home Assistant **2024.1** or newer
- An **RS-485 adapter** — either TCP/Ethernet (recommended) or direct USB serial
- Two-wire connection to the EasyTouch RS-485 bus

## Setup

1. Install via HACS or copy `custom_components/pentair_easytouch/` to your HA config directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Pentair EasyTouch**.
4. Choose **TCP** or **Serial** and enter your adapter's connection details.
5. Entities appear automatically as the controller broadcasts status (~30 seconds).

## What You Get

| Platform | What it controls |
|----------|-----------------|
| **Switch** | Circuits and features (pumps, waterfalls, spillovers) |
| **Light** | IntelliBrite lights with color modes |
| **Climate** | Pool/spa heat mode and setpoint |
| **Sensor** | Temperatures, pump RPM/watts/flow, salt level |
| **Binary Sensor** | Freeze protection, pump running, chlorinator active |
| **Number** | Chlorinator pool/spa output setpoint |
| **Select** | Heat mode selector |

## How It Works

The integration passively listens to the EasyTouch RS-485 bus. The controller broadcasts full status every 1–2 seconds, so entities update in real time with no polling. Commands are injected as properly framed RS-485 packets.

## Troubleshooting

Enable debug logging:

```yaml
logger:
  logs:
    custom_components.pentair_easytouch: debug
```

Download diagnostics from **Settings → Devices & Services → Pentair EasyTouch → ⋮ → Download diagnostics**.
