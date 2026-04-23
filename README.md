
# SDN Packet Logger — Jackfruit Mini Project

## Overview

A secure networked application that:
- Simulates an **SDN Controller** generating `packet_in` events
- **Captures and logs packet headers** (src/dst IP, MAC, port, protocol)
- **Identifies protocol types** (TCP / UDP / ICMP)
- Exposes a **TLS 1.2+ TCP server** and **HMAC-authenticated UDP server**
- Supports **multiple concurrent clients**
- Maintains a **rotating JSON log** and **live CLI display**
