# CyberSniff-SecureOT
A sniffing tool POC that sniffs a virtual network


## App Structure
```
app   /
      / plc
            /
            plc.py
            offline_packages /
      / sender
            /
            log_chunk*.jsonl
            integrity.py
            log_mangager.py
            client.py
            config.py
            certs /
      / server
            /
            config.py
            integrity.py
            server.py
            generate_certs.py
            certs /
      / simulation
            /
            Dockerfile
            docker-compose.yml
            generate_compose.py
            slave.py
      / sniffer
            /
            sniffer.py
            LOG_FILE.jsonl
```
## Physical Structure
```
Laptop: Server - - - - ⌉
                wlan0: mTLS
                       |
   SPAN      | Port 1: Sniffer 
Switch - - - | Port 2: Slave Simulation
   Mirrored  | Port 3: PLC Simulation
```         
## Prerequisites
- Docker
- Python3 version:
- Pymodbus 3.5.2
- Scapy
- Managed Switch
- 3 Raspberry Pi - One capable of wifi communication



