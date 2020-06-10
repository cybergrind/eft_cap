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
from eft_cap.msg_level import GLOBAL, PLAYERS, Player, Map
import logging
from fan_tools.python import rel_path


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

    async def draw_table(self, me, players, dead_players, loot):
        for ws in self.ws_clients:
            await ws.send_json(
                {
                    'type': 'DRAW_TABLE',
                    'me': me,
                    'players': players,
                    'deadPlayers': dead_players,
                    'loot': loot,
                }
            )

    async def update_loop(self):
        while True:
            try:
                await self.send_update()
            except:
                self.log.exception('While update')
            await asyncio.sleep(1)

    def player_to_row(self, player, classes=[]):
        return {
            'row': [
                player._cached_dist,
                f'{player.vdist()}',
                player.angle(),
                str(player),
                player.rnd_pos,
                str(player.is_alive),
            ],
            'className': ' '.join(classes),
        }

    def player_to_json(self, player: Player):
        if not player:
            return None

        return {
            'name': str(player),
            'dist': player.dist(),
            'angle': player.angle(),
            'vdist': player.vdist(),
            'pos': player.rnd_pos,
            'group': player.group_id,
            'loot_price': player.loot_price,
            'is_alive': player.is_alive,
            'is_npc': player.is_npc,
            'is_scav': player.is_scav,
            'me': player.me,
            'wanted': getattr(player, 'wanted', False),
        }

    async def send_update(self):
        players = []
        dead_players = []
        player: Player
        me = GLOBAL['me']
        my_group = me.group_id if me else None
        players = []

        player: Player
        for player in PLAYERS.values():

            if player.me:
                continue

            players.append(self.player_to_json(player))
            continue

        GLOBAL['loot'].update_location()
        loot = GLOBAL['loot'].display_loot()
        await self.draw_table(self.player_to_json(me), players, dead_players, loot)
        await self.map_update()

    async def map_update(self):
        map: Map = GLOBAL['map']
        if not map:
            return
        for ws in self.ws_clients:
            await ws.send_json({'type': 'DRAW_EXITS', 'exits': map.exits})
