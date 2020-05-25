import asyncio
from pprint import pprint
import sys
import json
import tkinter as tk
import time

sys.path.append('.')

# dest 17000:17100
# src 56000:61000
from eft_cap.network_base import NetworkTransport

dest_filter = '(udp.DstPort >= 17000 and udp.DstPort <= 17100)'
src_filter = '(udp.SrcPort >= 56000 and udp.SrcPort <= 61000)'

s1 = '(udp.DstPort >= 17000 and udp.DstPort <= 17100)'
d1 = '(udp.SrcPort >= 17000 and udp.SrcPort <= 17100)'


def capture():
    import pydivert  # linux support
    with pydivert.WinDivert(f'{s1} or {d1}') as w:
        for packet in w:
            print(f'Packet: {packet}')
            with open('packet.bin', 'wb') as f:
                f.write(packet.payload)
            break


def n_separated_file(name):
    with open(name) as f:
        line = f.readline()
        while line:
            yield json.loads(line)
            line = f.readline()


def from_file():
    for packet in n_separated_file('./shark_cap/cap_03.json'):
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

class App(tk.Tk):
    def __init__(self, loop):
        self.loop = loop
        self.__cells = []
        super().__init__()

        loop.create_task(self.update_loop())
        self.draw_table(
            [f'Head: {i}' for i in range(10)],
            [[f'Inner: {x}/{y}' for x in range(10)] for y in range(6)]
        )

    def draw_table(self, headers, rows):
        for w in self.__cells:
            w.destroy()
        self.__cells = []
        for header_col, text in enumerate(headers):
            self.draw_cell(0, header_col, text)
        for row_1, row in enumerate(rows):
            for col, text in enumerate(row):
                self.draw_cell(row_1 + 1, col, text)

    def draw_cell(self, row, col, text):
        b = tk.Label(self, text=f' {text} ', borderwidth=1, relief='groove')
        b.grid(row=row, column=col)
        self.__cells.append(b)

    async def update_loop(self):
        while True:
            print('Update loop')
            self.draw_table(
                [f'Head: {i}' for i in range(10)],
                [[f'Inner: {x}/{y}/ {time.time()}' for x in range(10)] for y in range(6)]
            )
            self.update()
            await asyncio.sleep(1)

    def destroy(self):
        self.loop.stop()
        super().destroy()

def main():
    p_source = from_file()
    for i in range(0):
        next(p_source)
    t = NetworkTransport(p_source)
    loop = asyncio.get_event_loop()
    # app = App(loop)
    loop.run_until_complete(t.run(limit=None))

if __name__ == '__main__':
    main()
