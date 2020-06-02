import asyncio
import pathlib
from sys import exit
import time
from pprint import pprint

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.websockets import WebSocket
from starlette.staticfiles import StaticFiles
import uvicorn
from eft_cap.msg_level import  GLOBAL, PLAYERS, Player
import logging
from fan_tools.python import  rel_path


class App:
    log = logging.getLogger('webserver')

    def __init__(self, loop: asyncio.BaseEventLoop):
        self.static = pathlib.Path(rel_path('../frontend/build', check=False))
        self.loop = loop
        self.app = Starlette(routes=self.routes, on_shutdown=[self.exit])
        self.config = uvicorn.config.Config(self.app, log_config=None, host='0.0.0.0', port=7999)
        self.server = uvicorn.Server(config=self.config)
        self.serve_task = loop.create_task(self.server.serve())
        self.update_task = loop.create_task(self.update_loop())
        self.ws_clients = []

    async def index(self, request):
        return FileResponse(self.static / 'index.html')

    async def status(self, request):
        return JSONResponse({'status': 'ok'})

    async def ws_endpoint(self, ws: WebSocket):
        await ws.accept()
        try:
            self.ws_clients.append(ws)
            while True:
                msg = await ws.receive_json()
                try:
                    await self.handle_msg(msg)
                except:
                    self.log.exception(f'During handle: {msg}')
        finally:
            self.ws_clients.remove(ws)

    async def handle_msg(self, msg):
        if msg['type'] == 'LOOT_HIDE':
            payload = msg['payload']
            GLOBAL['loot'].hide(payload['id'])

    @property
    def routes(self):
        return [
            Route('/', self.index),
            Route('/status', endpoint=self.status),
            Mount('/static', app=StaticFiles(directory=self.static)),
            WebSocketRoute('/ws', self.ws_endpoint),
        ]

    def exit(self):
        self.log.warning('Stopping loop...')
        for f in GLOBAL['on_exit']:
            try:
                f()
            except:
                pass
        self.server.should_exit = True
        self.server.force_exit = True
        self.update_task.cancel()
        self.serve_task.cancel()
        self.loop.stop()
        exit(0)

    async def draw_table(self, head, table):
        for ws in self.ws_clients:
            await ws.send_json({'type': 'DRAW_TABLE', 'rows': table, 'head': head})

    async def update_loop(self):
        while True:
            try:
                await self.send_update()
            except:
                self.log.exception('While update')
            await asyncio.sleep(1)

    async def send_update(self):
        players = []
        dead_players = []
        player: Player
        me = GLOBAL['me']
        my_group = me.group_id if me else None

        for player in PLAYERS.values():
            is_alive = player.is_alive
            classes = []
            dist = player.dist()

            if is_alive:
                classes.append('alive')
            else:
                classes.append('dead')

            if player.is_npc:
                classes.append('npc')
            else:
                classes.append('player')

            if player.is_scav:
                classes.append('scav')

            if player.group_id and player.group_id != -1:
                if player.group_id == my_group:
                    classes.append('my_group')
                else:
                    classes.append('other_group')

            if hasattr(player, 'wanted') and player.is_scav:
                classes.append('player_wanted')
                # pprint(player)
                # exit(9)

            if dist == 0 or (my_group and player.group_id and player.group_id == my_group):
                pass
            elif dist < 50:
                classes.append('brawl')
            elif dist < 150:
                classes.append('nearby')

            row = {
                'row': [
                dist, f'{player.vdist()}', player.angle(), str(player),
                str(player.rnd_pos), str(is_alive)
                ],
                'className': ' '.join(classes)
            }
            if player.is_alive:
                players.append(row)
            else:
                dead_players.append(row)
        players = sorted(players, key=lambda x: x['row'][0])
        dead_players = sorted(dead_players, key=lambda x: x['row'][0])[:4]
        GLOBAL['loot'].update_location()
        loot = GLOBAL['loot'].display_loot()
        await self.draw_table(
            ['Dist', 'VDist', 'Angle', 'Name LVL/Frac/Type/Party', 'Coord', 'Is Alive'],
            # [f'Head: {i}' for i in range(10)],
            # [[f'Inner: {x}/{y}/ {time.time()}' for x in range(10)] for y in range(6)]
            [*players, *dead_players, *loot]
        )
