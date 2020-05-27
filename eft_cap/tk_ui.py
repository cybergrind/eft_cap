import asyncio
import logging
import tkinter as tk

from eft_cap.msg_level import PLAYERS, Player


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
            players = []
            dead_players = []

            player: Player
            for player in PLAYERS.values():
                row = [
                    f'{player.dist()}', f'{player.vdist()}', str(player), str(player.rnd_pos), str(player.is_alive)
                ]
                if player.is_alive:
                    players.append(row)
                else:
                    dead_players.append(row)
            players = sorted(players)
            dead_players = sorted(dead_players)

            self.draw_table(
                ['Dist', 'VDist', 'Name', 'Coord', 'Is Alive'],
                # [f'Head: {i}' for i in range(10)],
                # [[f'Inner: {x}/{y}/ {time.time()}' for x in range(10)] for y in range(6)]
                [*players, *dead_players]
            )
            self.update()
            await asyncio.sleep(0.1)

    def destroy(self):
        self.loop.stop()
        super().destroy()
