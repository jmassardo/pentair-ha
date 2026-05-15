"""Protocol constants for the Pentair EasyTouch RS485 integration."""

DOMAIN = "pentair_easytouch"

# ---------------------------------------------------------------------------
# RS485 addresses
# ---------------------------------------------------------------------------
BROADCAST_ADDR = 15
CONTROLLER_ADDR = 16
REMOTE_ADDR = 33  # Default address njsPC/this integration uses (configurable)

# Pump addresses range from 96-111 (pumps 1-16)
PUMP_ADDR_START = 96
PUMP_ADDR_END = 111

# Heater addresses range from 112-127
HEATER_ADDR_START = 112
HEATER_ADDR_END = 127

# IntelliChem addresses range from 144-158
INTELLICHEM_ADDR_START = 144
INTELLICHEM_ADDR_END = 158

# IntelliValve address
INTELLIVALVE_ADDR = 12

# Chlorinator addresses range from 80-83
CHLORINATOR_ADDR_START = 80
CHLORINATOR_ADDR_END = 83

# ---------------------------------------------------------------------------
# Packet framing bytes
# ---------------------------------------------------------------------------
PREAMBLE = bytes([255, 0, 255])
MSG_START = bytes([165])

# Chlorinator framing
CHLOR_HEADER_START = bytes([16, 2])
CHLOR_TERMINATOR = bytes([16, 3])

# ---------------------------------------------------------------------------
# Action codes - inbound (status / broadcast)
# ---------------------------------------------------------------------------
ACTION_STATUS = 2  # Equipment status broadcast (~29-byte payload)
ACTION_DATETIME = 5  # Date/time broadcast
ACTION_PUMP_STATUS = 7  # Pump status response
ACTION_HEAT_STATUS = 8  # Heat/temperature status
ACTION_CUSTOM_NAMES = 10  # Custom name definitions
ACTION_CIRCUIT_NAMES = 11  # Circuit name/function definitions
ACTION_SCHEDULES = 17  # Schedule definitions
ACTION_SCHEDULES_ALT = 18  # Schedule definitions (alternate)
ACTION_SPA_SIDE_REMOTE = 22  # Spa-side remote config
ACTION_PUMP_STATUS_BROADCAST = 23  # Pump status broadcast
ACTION_PUMP_CONFIG = 24  # Pump config broadcast
ACTION_INTELLICHLOR = 25  # IntelliChlor status broadcast
ACTION_VALVES = 29  # Valve config broadcast
ACTION_HIGH_SPEED_CIRCUITS = 30  # High-speed circuit config
ACTION_IS4_IS10 = 32  # IS4/IS10 config
ACTION_SOLAR_HEATPUMP = 34  # Solar / heat pump config
ACTION_DELAYS = 35  # Delays broadcast
ACTION_LIGHT_GROUP_POSITIONS = 39  # Light group positions
ACTION_SETTINGS = 40  # Settings broadcast
ACTION_CIRCUIT_GROUPS = 41  # Circuit group definitions
ACTION_INTELLIBRITE = 96  # IntelliBrite light mode

# ---------------------------------------------------------------------------
# Action codes - outbound (commands)
# ---------------------------------------------------------------------------
ACTION_CANCEL_DELAY = 131  # Cancel delay
ACTION_SET_DATETIME = 133  # Set date/time
ACTION_SET_CIRCUIT = 134  # Set circuit on/off
ACTION_SET_HEAT_SETPOINT = 136  # Set heat setpoint
ACTION_SET_HEATPUMP = 137  # Set heat pump
ACTION_SET_CUSTOM_NAME = 138  # Set custom name
ACTION_SET_CIRCUIT_FUNC = 139  # Set circuit name/function
ACTION_SET_HEATPUMP2 = 144  # Set heat pump (alt)
ACTION_SET_SCHEDULE = 145  # Set schedule
ACTION_SET_INTELLICHEM = 146  # Set IntelliChem
ACTION_SET_SPA_SIDE_REMOTE = 150  # Set spa-side remote
ACTION_SET_PUMP_CONFIG = 152  # Set pump config
ACTION_SET_CHLORINATOR = 153  # Set IntelliChlor
ACTION_SET_PUMP_CONFIG_EXT = 155  # Set pump config (extended)
ACTION_SET_VALVES = 157  # Set valves
ACTION_SET_HIGH_SPEED_CIRCUITS = 158  # Set high-speed circuits
ACTION_SET_IS4_IS10 = 160  # Set IS4/IS10
ACTION_SET_QUICKTOUCH = 161  # Set QuickTouch
ACTION_SET_SOLAR_HEATPUMP = 162  # Set solar/heat pump
ACTION_SET_DELAY = 163  # Set delay
ACTION_SET_LIGHT_GROUP = 167  # Set light group/positions
ACTION_SET_HEAT_MODE = 168  # Set heat mode

# ---------------------------------------------------------------------------
# Action codes - request (get config)
# ---------------------------------------------------------------------------
ACTION_GET_DATETIME = 197  # Get date/time
ACTION_GET_HEAT_TEMP = 200  # Get heat/temperature
ACTION_GET_CUSTOM_NAMES = 202  # Get custom names
ACTION_GET_CIRCUITS = 203  # Get circuits
ACTION_GET_SCHEDULES = 209  # Get schedules
ACTION_GET_SPA_SIDE_REMOTE = 214  # Get spa-side remotes
ACTION_GET_PUMP_STATUS = 215  # Get pump status
ACTION_GET_PUMP_CONFIG = 216  # Get pump config
ACTION_GET_INTELLICHLOR = 217  # Get IntelliChlor config
ACTION_GET_VALVES = 221  # Get valves
ACTION_GET_HIGH_SPEED_CIRCUITS = 222  # Get high-speed circuits
ACTION_GET_IS4_IS10 = 224  # Get IS4/IS10
ACTION_GET_SOLAR_HEATPUMP = 226  # Get solar/heat pump
ACTION_GET_DELAYS = 227  # Get delays
ACTION_GET_LIGHT_GROUP_POS = 231  # Get light group positions
ACTION_GET_SETTINGS = 232  # Get settings
ACTION_GET_CIRCUIT_GROUPS = 233  # Get circuit groups
ACTION_GET_VERSION = 252  # Get version
ACTION_GET_VERSION_ALT = 253  # Get version (alt)

# ---------------------------------------------------------------------------
# Chlorinator sub-protocol action codes
# ---------------------------------------------------------------------------
CHLOR_ACTION_CONTROL = 0  # OCP → Chlorinator: control
CHLOR_ACTION_ACK = 1  # Chlorinator → OCP: ack
CHLOR_ACTION_MODEL = 3  # Chlorinator → OCP: model/name
CHLOR_ACTION_SET_OUTPUT = 17  # OCP → Chlorinator: set output %
CHLOR_ACTION_STATUS = 18  # Chlorinator → OCP: salt + status
CHLOR_ACTION_KEEPALIVE = 19  # iChlor keep-alive
CHLOR_ACTION_GET_MODEL = 20  # OCP → Chlorinator: get model
CHLOR_ACTION_SET_OUTPUT_ALT = 21  # OCP → Chlorinator: set output (/10)
CHLOR_ACTION_ICHLOR_STATUS = 22  # iChlor → OCP: output + temp

# ---------------------------------------------------------------------------
# Pump sub-protocol action codes
# ---------------------------------------------------------------------------
PUMP_ACTION_SET_SPEED = 1  # Set pump speed / detect type
PUMP_ACTION_STATUS = 7  # Pump status response
PUMP_ACTION_VSF_1 = 9  # VSF pump type detection
PUMP_ACTION_VSF_2 = 10  # VSF pump type detection

# ---------------------------------------------------------------------------
# Serial port defaults
# ---------------------------------------------------------------------------
DEFAULT_BAUD_RATE = 9600
DEFAULT_DATA_BITS = 8
DEFAULT_PARITY = "none"
DEFAULT_STOP_BITS = 1

# ---------------------------------------------------------------------------
# TCP defaults
# ---------------------------------------------------------------------------
DEFAULT_TCP_PORT = 9801

# ---------------------------------------------------------------------------
# Reconnection defaults
# ---------------------------------------------------------------------------
RECONNECT_MIN_DELAY = 1.0  # seconds
RECONNECT_MAX_DELAY = 60.0  # seconds
RECONNECT_BACKOFF_FACTOR = 2.0
