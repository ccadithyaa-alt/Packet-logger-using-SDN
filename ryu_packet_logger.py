from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.lib.packet import packet, ethernet, ipv4, tcp, udp
import socket, json

LOGGER_HOST = "127.0.0.1"
LOGGER_PORT = 9999   # we'll open this in your packet_logger

class RyuPacketLogger(app_manager.RyuApp):
    OFP_VERSIONS = [0x04]  # OpenFlow 1.3

    def send_to_logger(self, data):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(json.dumps(data).encode(), (LOGGER_HOST, LOGGER_PORT))
            s.close()
        except Exception as e:
            print("Logger send error:", e)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocol(ethernet.ethernet)
        ip = pkt.get_protocol(ipv4.ipv4)

        if not ip:
            return

        proto = "OTHER"
        if pkt.get_protocol(tcp.tcp):
            proto = "TCP"
        elif pkt.get_protocol(udp.udp):
            proto = "UDP"

        data = {
            "src": ip.src,
            "dst": ip.dst,
            "proto": proto
        }

        print("Packet:", data)
        self.send_to_logger(data)