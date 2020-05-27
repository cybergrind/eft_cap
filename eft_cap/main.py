#!/usr/bin/env python3
import argparse
import logging
import asyncio
import sys
import json

sys.path.append('.')
from eft_cap.tk_ui import App
from eft_cap.network_base import NetworkTransport

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('eft_cap.main')


def parse_args():
    parser = argparse.ArgumentParser(description='DESCRIPTION')
    parser.add_argument('packets_file', nargs='?')
    parser.add_argument('--packet-delay', type=float, default=0)
    parser.add_argument('--tk', action='store_true')
    # parser.add_argument('-m', '--mode', default='auto', choices=['auto', 'manual'])
    # parser.add_argument('-l', '--ll', dest='ll', action='store_true', help='help')
    return parser.parse_args()


# dest 17000:17100
# src 56000:61000
dest_filter = '(udp.DstPort >= 17000 and udp.DstPort <= 17100)'
src_filter = '(udp.SrcPort >= 56000 and udp.SrcPort <= 61000)'

s1 = '(udp.DstPort >= 16900 and udp.DstPort <= 17100)'
d1 = '(udp.SrcPort >= 16900 and udp.SrcPort <= 17100)'


async def capture():
    import pydivert  # linux support
    with pydivert.WinDivert(f'{s1} or {d1}') as w:
        for packet in w:
            yield {
                'data': packet.payload,
                'incoming': packet.is_inbound,
            }
            # print(f'Packet: {packet}')
            # with open('packet.bin', 'wb') as f:
            #     f.write(packet.payload)
            # break


def n_separated_file(name):
    with open(name) as f:
        line = f.readline()
        while line:
            yield json.loads(line)
            line = f.readline()


async def from_file(args):
    for packet in n_separated_file(args.packets_file):
        udp = packet["_source"]["layers"]['udp']
        ip = packet["_source"]["layers"]['ip']
        if 'data' not in packet["_source"]["layers"]:
            continue
        data = bytes.fromhex(packet["_source"]["layers"]["data"]["data.data"].replace(':', ''))
        # print(f'{data} / {udp}')
        yield {
            'data': data,
            'incoming': ip['ip.dst'].startswith('192.168.88.')
        }
        await asyncio.sleep(args.packet_delay)


def main():
    args = parse_args()
    if args.packets_file:
        p_source = from_file(args)
    else:
        p_source = capture()

    for i in range(0):
        next(p_source)
    t = NetworkTransport(p_source)
    loop = asyncio.get_event_loop()
    if args.tk:
        app = App(loop)
    loop.run_until_complete(t.run(limit=None))



if __name__ == '__main__':
    main()
