"""
sdn_controller.py — Simulated SDN Controller (OpenFlow-style)
=============================================================
Simulates an SDN controller that fires packet_in events whenever
a new flow arrives on the virtual switch.  The Packet Logger
subscribes to these events via an internal publish/subscribe bus.

Architecture:
  SDNController  ──packet_in──▶  EventBus  ──▶  PacketLoggerApp
"""

import threading
import time
import random
import socket
import struct
import ipaddress
from dataclasses import dataclass, field
from typing import Callable, List, Dict
from enum import IntEnum


# ---------------------------------------------------------------------------
# Protocol constants (matching common EtherTypes / IP protocol numbers)
# ---------------------------------------------------------------------------
class EtherType(IntEnum):
    IPv4 = 0x0800
    IPv6 = 0x86DD
    ARP  = 0x0806


class IPProto(IntEnum):
    ICMP = 1
    TCP  = 6
    UDP  = 17


PROTO_NAME: Dict[int, str] = {
    IPProto.ICMP: "ICMP",
    IPProto.TCP:  "TCP",
    IPProto.UDP:  "UDP",
}


# ---------------------------------------------------------------------------
# Simulated Packet Header
# ---------------------------------------------------------------------------
@dataclass
class PacketHeader:
    """Represents the header information extracted from a captured packet."""
    timestamp:   float
    src_mac:     str
    dst_mac:     str
    eth_type:    int          # EtherType (IPv4 / IPv6 / ARP)
    src_ip:      str
    dst_ip:      str
    ip_proto:    int          # TCP / UDP / ICMP
    src_port:    int
    dst_port:    int
    payload_len: int
    switch_id:   int          # Which virtual switch saw this packet

    @property
    def protocol_name(self) -> str:
        return PROTO_NAME.get(self.ip_proto, f"PROTO-{self.ip_proto}")

    def summary(self) -> str:
        return (
            f"[{time.strftime('%H:%M:%S', time.localtime(self.timestamp))}] "
            f"SW-{self.switch_id:02d}  "
            f"{self.src_ip}:{self.src_port:<5}  →  "
            f"{self.dst_ip}:{self.dst_port:<5}  "
            f"{self.protocol_name:<4}  {self.payload_len} B"
        )


# ---------------------------------------------------------------------------
# Event Bus — lightweight pub/sub
# ---------------------------------------------------------------------------
class EventBus:
    """
    Simple thread-safe publish/subscribe bus.
    Subscribers register a callable; publishers emit events.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: List[Callable[[PacketHeader], None]] = []

    def subscribe(self, handler: Callable[[PacketHeader], None]) -> None:
        with self._lock:
            self._subscribers.append(handler)

    def publish(self, pkt: PacketHeader) -> None:
        """Dispatch packet_in event to all registered handlers."""
        with self._lock:
            handlers = list(self._subscribers)
        for handler in handlers:
            try:
                handler(pkt)
            except Exception as exc:
                print(f"[EventBus] Handler error: {exc}")


# ---------------------------------------------------------------------------
# SDN Controller
# ---------------------------------------------------------------------------
class SDNController(threading.Thread):
    """
    Simulates an OpenFlow SDN controller.

    In a real deployment this would speak the OpenFlow protocol over a TCP
    socket (port 6633/6653).  Here we simulate flow events by generating
    pseudo-random packet headers that represent 'packet_in' messages —
    i.e. packets that hit the controller because the switch had no matching
    flow rule yet.
    """

    SWITCH_COUNT = 4          # number of simulated switches

    def __init__(self, bus: EventBus, rate: float = 1.0):
        """
        Parameters
        ----------
        bus  : EventBus to publish packet_in events on
        rate : average packets-per-second to generate (float)
        """
        super().__init__(daemon=True, name="SDNController")
        self.bus      = bus
        self.rate     = rate          # packets / second
        self._running = threading.Event()
        self._running.set()

    # ------------------------------------------------------------------
    # Helpers to fabricate realistic-looking headers
    # ------------------------------------------------------------------
    @staticmethod
    def _rand_mac() -> str:
        octets = [random.randint(0x00, 0xFF) for _ in range(6)]
        octets[0] &= 0xFE   # clear multicast bit
        return ":".join(f"{b:02x}" for b in octets)

    @staticmethod
    def _rand_ipv4() -> str:
        # Use RFC-5737 documentation ranges so these look believable
        prefixes = ["192.0.2", "198.51.100", "203.0.113", "10.0", "172.16"]
        return f"{random.choice(prefixes)}.{random.randint(1, 254)}"

    @staticmethod
    def _rand_proto() -> int:
        # Weighted towards TCP (most common), then UDP, then ICMP
        return random.choices(
            [IPProto.TCP, IPProto.UDP, IPProto.ICMP],
            weights=[60, 35, 5]
        )[0]

    def _make_packet(self) -> PacketHeader:
        proto = self._rand_proto()
        # ICMP doesn't have meaningful port numbers
        src_port = random.randint(1024, 65535) if proto != IPProto.ICMP else 0
        # Use well-known destination ports to make traces interesting
        if proto == IPProto.TCP:
            dst_port = random.choice([80, 443, 22, 8080, 3306, 5432, 6379])
        elif proto == IPProto.UDP:
            dst_port = random.choice([53, 67, 123, 514, 5353])
        else:
            dst_port = 0

        return PacketHeader(
            timestamp   = time.time(),
            src_mac     = self._rand_mac(),
            dst_mac     = self._rand_mac(),
            eth_type    = EtherType.IPv4,
            src_ip      = self._rand_ipv4(),
            dst_ip      = self._rand_ipv4(),
            ip_proto    = proto,
            src_port    = src_port,
            dst_port    = dst_port,
            payload_len = random.randint(40, 1500),
            switch_id   = random.randint(1, self.SWITCH_COUNT),
        )

    # ------------------------------------------------------------------
    # Thread main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        print(f"[SDNController] Started — generating ~{self.rate:.1f} pkt/s "
              f"across {self.SWITCH_COUNT} virtual switches")
        while self._running.is_set():
            pkt = self._make_packet()
            self.bus.publish(pkt)                  # fire packet_in event
            # Poisson-distributed inter-arrival time gives realistic bursts
            sleep_time = random.expovariate(self.rate)
            time.sleep(min(sleep_time, 2.0))        # cap at 2 s to stay lively

    def stop(self) -> None:
        self._running.clear()
        print("[SDNController] Stopped")
