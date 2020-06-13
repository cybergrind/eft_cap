#!/usr/bin/env python3
import argparse
import logging
import asyncio
import sys
import json
from multiprocessing import Process, Queue
from queue import Empty
import time

sys.path.append('.')
from eft_cap.tk_ui import App
from eft_cap.network_base import NetworkTransport
from eft_cap.msg_level import GLOBAL
from eft_cap import webserver


logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('eft_cap.main')


def parse_args():
    parser = argparse.ArgumentParser(description='DESCRIPTION')
    parser.add_argument('packets_file', nargs='?')
    parser.add_argument('--packet-delay', type=float, default=0)
    parser.add_argument('--tk', action='store_true')
    parser.add_argument('--web', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--skip', type=int, default=None)
    # parser.add_argument('-m', '--mode', default='auto', choices=['auto', 'manual'])
    # parser.add_argument('-l', '--ll', dest='ll', action='store_true', help='help')
    return parser.parse_args()


# dest 17000:17100
# src 56000:61000
dest_filter = '(udp.DstPort >= 17000 and udp.DstPort <= 17100)'
src_filter = '(udp.SrcPort >= 56000 and udp.SrcPort <= 61000)'

s1 = '(udp.DstPort >= 16900 and udp.DstPort <= 17100)'
d1 = '(udp.SrcPort >= 16900 and udp.SrcPort <= 17100)'


async def capture_tzsp():
    from eft_cap.tzsp import run
    q = asyncio.Queue()
    asyncio.create_task(run(q.put_nowait))
    while True:
        yield await q.get()


def capture_diver(q: Queue):
    import pydivert  # linux support
    with pydivert.WinDivert(f'{s1} or {d1}', flags=pydivert.Flag.SNIFF) as w:
        for packet in w:
            # print(f'Packet: PL={len(packet.payload)} PCKT: {packet} {len(packet.udp.raw)}')
            q.put_nowait(
                {
                    'data': packet.payload,
                    'incoming': packet.is_inbound,
                }
            )

def capture_pcap(q: Queue):
    import pcap
    import scapy
    from scapy.layers.l2 import Ether
    from scapy.all import load_layer
    load_layer('inet')
    s = pcap.pcap('eno1', promisc=True, immediate=True)
    s.setfilter('udp portrange 16900-17100')

    def raw_to_dict(data):
        ue = Ether(data)
        ip = ue.payload

        if ip.version != 4:
            return

        if ip.proto != 17:
            return
        udp = ip.payload
        if udp.len == 0:
            return
        if not isinstance(udp.payload, scapy.packet.Raw):
            return
        payload = udp.load
        return {
            'incoming': ip.dst.startswith('192.168.'),
            'data': payload,
            'src_port': udp.sport,
            'dst_port': udp.dport,
        }
    for t, data in s:
        dct = raw_to_dict(data)
        if data:
            q.put_nowait(dct)


def gen_kill(p):
    def _inner():
        log.warning('Killing divert process...')
        return p.kill()
    return _inner


async def capture():
    q = Queue()
    target = capture_diver
    if sys.platform == 'linux':
        target = capture_pcap
    p = Process(target=target, args=(q,))
    p.start()
    t = time.time()
    GLOBAL['on_exit'].append(gen_kill(p))
    GLOBAL['get_qsize'] = lambda: q.qsize()
    try:
        while True:
            try:
                msg = q.get(block=False)
                t1 = time.time()
                if t1 - t > 15:
                    t = t1
                    log.warning(f'Queue size: {q.qsize()}')
                yield msg
            except Empty:
                t1 = time.time()
                if t1 - t > 60:
                    t = t1
                    log.warning('Empty queue')
                pass
            await asyncio.sleep(0)
    finally:
        print(f'Call terminate: {p}')
        p.terminate()


def n_separated_file(name):
    with open(name) as f:
        line = f.readline()
        while line:
            yield json.loads(line)
            line = f.readline()


def from_shark(packet):
    udp = packet["_source"]["layers"]['udp']
    ip = packet["_source"]["layers"]['ip']
    if 'data' not in packet["_source"]["layers"]:
        return
    data = bytes.fromhex(packet["_source"]["layers"]["data"]["data.data"].replace(':', ''))
    return {
        'data': data,
        'incoming': ip['ip.dst'].startswith('192.168')
    }


def from_log(packet):
    data = bytes.fromhex(packet['data'].replace(':', ''))
    return {
        **packet,
        'data': data,
    }


async def from_file(args):
    decoder = None
    for packet in n_separated_file(args.packets_file):
        if decoder is None:
            if 'incoming' in packet:
                decoder = from_log
            else:
                decoder = from_shark
        ret = decoder(packet)
        if ret:
            yield ret
        await asyncio.sleep(args.packet_delay)


def run(args, p_source):
    t = NetworkTransport(p_source, args)
    loop = asyncio.get_event_loop()
    if args.tk:
        app = App(loop)
    elif args.web:
        app = webserver.App(loop)
    transport_task = loop.create_task(t.run(limit=args.limit))
    GLOBAL['on_exit'].append(lambda: transport_task.cancel())
    loop.run_until_complete(transport_task)


def main():
    args = parse_args()
    if args.packets_file:
        p_source = from_file(args)
    else:
        p_source = capture()

    if args.profile:
        import yappi
        yappi.set_clock_type("WALL")
        with yappi.run():
            run(args, p_source)
        stats = yappi.get_func_stats()
        stats.save('profile.prof', type='pstat')
    else:
        run(args, p_source)




if __name__ == '__main__':
    main()
