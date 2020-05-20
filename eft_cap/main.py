import asyncio
from pprint import pprint
import sys
import pydivert
import json

sys.path.append('.')

# dest 17000:17100
# src 56000:61000
from eft_cap.network_base import NetworkTransport

dest_filter = '(udp.DstPort >= 17000 and udp.DstPort <= 17100)'
src_filter = '(udp.SrcPort >= 56000 and udp.SrcPort <= 61000)'

s1 = '(udp.DstPort >= 17000 and udp.DstPort <= 17100)'
d1 = '(udp.SrcPort >= 17000 and udp.SrcPort <= 17100)'

def capture():
    with pydivert.WinDivert(f'{s1} or {d1}') as w:
        for packet in w:
            print(f'Packet: {packet}')
            with open('packet.bin', 'wb') as f:
                f.write(packet.payload)
            break

def from_file():
    with open('./shark_cap/d2.json') as f:
        packets = json.load(f)
    for packet in packets:
        udp = packet["_source"]["layers"]['udp']
        ip = packet["_source"]["layers"]['ip']
        data = bytes.fromhex(packet["_source"]["layers"]["data"]["data.data"].replace(':', ''))
        # print(f'{data} / {udp}')
        yield {
            'data': data,
            'incoming': ip['ip.dst'].startswith('192.168.88.')
        }


def main():
    p_source = from_file()
    t = NetworkTransport(p_source)
    asyncio.run(t.run(limit=None))

if __name__ == '__main__':
    main()
