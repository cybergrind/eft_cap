#!/usr/bin/env python3
import argparse
import logging
import asyncio
from pprint import pprint
import sys
import json
import tkinter as tk
import time

sys.path.append('.')


from eft_cap.network_base import NetworkTransport
from eft_cap.msg_level import PLAYERS


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
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


class App(tk.Tk):
    log = logging.getLogger('TK.APP')

    def __init__(self, loop):
        self.loop = loop
        self.__cells = []
        self.rows = []
        super().__init__()

        loop.create_task(self.update_loop())

    def add_rows(self, need_rows, num_cols):
        num_rows = len(self.rows)
        self.log.debug(f'Going to add: {need_rows} rows. Curr: {num_rows} rows')
        for row_idx in range(num_rows, need_rows):
            row = []
            for col_idx in range(num_cols):
                row.append(self.draw_cell(row_idx, col_idx, '<EMPTY>'))
            self.rows.append(row)
            self.log.debug(f'Add {row_idx}')
        self.log.debug(f'Now we have: {len(self.rows)} rows')

    def remove_rows(self, need_rows):
        num_rows = len(self.rows)
        assert need_rows < num_rows
        self.log.debug(f'Going to remove: {num_rows - need_rows} rows')
        for i in range(num_rows - need_rows):
            row = self.rows.pop()
            for col in row:
                col.destroy()

    def draw_table(self, headers, rows):
        num_cols = len(headers)

        num_rows = len(self.rows)
        need_rows = len(rows) + 1
        self.log.debug(f'Num: {num_rows} Need: {need_rows}')
        if num_rows < need_rows:
            self.add_rows(need_rows, num_cols)
            print(f'Add: {rows}')
        elif num_rows > need_rows:
            self.remove_rows(need_rows)
            print(f'Remove: {rows}')
        assert len(self.rows) == need_rows

        self.log.debug(f'NUM ROWS: {len(self.rows)} / {len(rows)}')
        for row_1, row in enumerate([headers, *rows]):
            for col, text in enumerate(row):
                self.log.debug(f'Row idx: {row_1}')
                cell = self.rows[row_1][col]
                cell.txt.set(f' {text} ')

    def draw_cell(self, row, col, text):
        var = tk.StringVar()
        b = tk.Label(self, textvariable=var, borderwidth=1, relief='groove')
        var.set(f' {text} ')
        b.grid(row=row, column=col)
        b.txt = var
        return b


    async def update_loop(self):
        while True:
            self.log.debug('Update loop')
            players = []
            dead_players = []

            for player in PLAYERS.values():
                row = [
                    player.dist(), str(player), str(player.rnd_pos), str(player.is_alive)
                ]
                if player.is_alive:
                    players.append(row)
                else:
                    dead_players.append(row)
            players = sorted(players)
            dead_players = sorted(dead_players)

            self.draw_table(
                ['Dist', 'Name', 'Coord', 'Is Alive'],
                # [f'Head: {i}' for i in range(10)],
                # [[f'Inner: {x}/{y}/ {time.time()}' for x in range(10)] for y in range(6)]
                [*players, *dead_players]
            )
            self.update()
            await asyncio.sleep(0.1)

    def destroy(self):
        self.loop.stop()
        super().destroy()


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
