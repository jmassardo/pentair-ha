"""Pentair EasyTouch RS485 protocol layer.

This package is a *pure-Python* implementation of the Pentair RS485
broadcast protocol.  It has **zero** Home Assistant dependencies so it
can be unit-tested and reused outside HA.
"""

from custom_components.pentair_easytouch.protocol.commands import CommandManager
from custom_components.pentair_easytouch.protocol.framing import (
    PacketFramer,
    build_packet,
)
from custom_components.pentair_easytouch.protocol.messages import MessageRouter
from custom_components.pentair_easytouch.protocol.transport import (
    BaseTransport,
    SerialTransport,
    TcpTransport,
)

__all__ = [
    "BaseTransport",
    "CommandManager",
    "MessageRouter",
    "PacketFramer",
    "SerialTransport",
    "TcpTransport",
    "build_packet",
]
