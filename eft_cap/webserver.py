import asyncio
import pathlib
from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount
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

    async def index(self, request):
        return FileResponse(self.static / 'index.html')

    async def status(self, request):
        return JSONResponse({'status': 'ok'})

    @property
    def routes(self):
        return [
            Route('/', self.index),
            Route('/status', endpoint=self.status),
            Mount('/static', app=StaticFiles(directory=self.static)),
        ]

    def exit(self):
        self.log.warning('Stopping loop...')
        for f in GLOBAL['on_exit']:
            try:
                f()
            except:
                pass
        self.loop.stop()

    async def update_loop(self):
        while True:
            players = []
            dead_players = []

            player: Player
            for player in PLAYERS.values():
                row = [
                    player.dist(), f'{player.vdist()}', player.angle(), str(player),
                    str(player.rnd_pos), str(player.is_alive)
                ]
                if player.is_alive:
                    players.append(row)
                else:
                    dead_players.append(row)
            players = sorted(players, key=lambda x: x[0])
            dead_players = sorted(dead_players, key=lambda x: x[0])[:4]
            GLOBAL['loot'].update_location()
            loot = GLOBAL['loot'].display_loot()

            self.draw_table(
                ['Dist', 'VDist', 'Angle', 'Name', 'Coord', 'Is Alive'],
                # [f'Head: {i}' for i in range(10)],
                # [[f'Inner: {x}/{y}/ {time.time()}' for x in range(10)] for y in range(6)]
                [*players, *dead_players, *loot]
            )
            await asyncio.sleep(1)
