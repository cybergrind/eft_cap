from __future__ import annotations

import copy
import json
import logging
import math
import time
import zlib
from pprint import pprint
import random
from typing import TYPE_CHECKING

import numpy as np

from eft_cap import bprint, split, split_16le
from eft_cap.bin_helpers import BitStream, ByteStream, FloatQuantizer, stream_from_le
from eft_cap.loot import (
    get_total_price,
    read_item,
    read_many_polymorph,
    read_polymorph,
    recurse_delete,
    recurse_item,
)
from eft_cap.trig_helpers import angle, dist, fwd_vector, norm_angle, quaternion_to_euler
from eft_cap.wanted import WANTED

if TYPE_CHECKING:
    from eft_cap.network_base import NetworkTransport


SERVER_INIT = 147
WORLD_SPAWN = 151
WORLD_UNSPAWN = 152  # TODO: maybe entry points here
SUBWORLD_SPAWN = 153
SUBWORLD_UNSPAWN = 154
PLAYER_SPAWN = 155
PLAYER_UNSPAWN = 156
OBSERVER_SPAWN = 157
OBSERVER_UNSPAWN = 158
BATTLE_EYE = 168
GAME_UPDATE = 170
log = logging.getLogger('msg_level')

Q_LOW = 0.001953125
Q_HIGH = 0.0009765625


class Loot:
    BY_DIST_NEARBY = 3
    BY_DIST_WANTED = 7
    BY_PRICE_EXPENSIVE = 10

    def __init__(self):
        self.by_id = {}
        self.by_dist = []
        self.by_dist_wanted = []
        self.by_price = []
        self.wanted = {}
        self.last_pos = np.array([0, 0, 0], np.float)
        self.hidden = {}
        self.skipped_updates = 0
        self.hard_skips = 0
        self.last_update = time.time()
        self.all_items = {}

    def hide(self, id):
        if id in self.by_id:
            item = self.by_id.pop(id)

        if id in self.wanted:
            self.wanted.pop(id)

        if id in self.hidden:
            return
        self.hidden[id] = item

        self.update_by_price()
        self.update_by_dist()

    def unhide(self, id):
        if id in self.hidden:
            item = self.hidden.pop(id)
        if id in self.by_id:
            return

        self.by_id[id] = item

        self.update_by_price()
        self.update_by_dist()

    def recursive_add(self, item, nesting, ctx, **kwargs):
        _id = item['id']
        if len(_id) not in (24, 25, 26, 27, 36):
            print(f'WRONG ID: {_id} / LEN: {len(_id)}')
            pprint(item)
            # exit(1)

        if nesting == 0:
            ctx['parent'] = item['id']
            item['parent'] = None
        elif nesting > 0:
            item['parent'] = ctx['parent']

        if 'crate' in ctx:
            item['crate'] = ctx['crate']
        elif 'player' in ctx:
            item['player'] = ctx['player']
        else:
            raise NotImplementedError

        if item['template_id'] in WANTED:
            item['wanted'] = True
            if 'crate' in ctx:
                crate = item['crate']
                crate['wanted'] = True
                self.wanted[crate['id']] = crate
            elif 'player' in ctx:
                ctx['player'].wanted = True

        if _id not in self.all_items:
            self.all_items[_id] = item

    def update_wanted_flat(self, crate):
        pass

    def store_item(self, item, ctx={}):
        recurse_item(item, self.recursive_add, ctx=ctx)

    def add_loot(self, msg, loot):
        if not loot:
            return
        for json_item in loot:

            if 'id' not in json_item:
                if 'item' not in json_item:
                    continue
                name = json_item['item']['name']
                x = int(json_item['position'][0])
                z = int(json_item['position'][2])
                json_item['id'] = f'{name}_{x}_{z}'
            self.store_item(json_item['item'], {'crate': json_item})
            total_price = json_item.get('total_price', 0)

            if 'wanted' in json_item:
                self.by_id[json_item['id']] = json_item
            elif self.is_ignored(json_item):
                self.hidden[json_item['id']] = json_item
            elif total_price < self.PRICE_TRESHOLD:
                self.hidden[json_item['id']] = json_item
            else:
                self.by_id[json_item['id']] = json_item
        self.update_by_price()

    def get_pid_in_grid(self, item, location):
        for grid in item['grid']:
            for grid_item in grid['items']:
                gl = grid_item['location']
                if gl['x'] == location['x'] and gl['y'] == location['y']:
                    # print(grid_item)
                    return grid_item['item']['id']
                # print(f'GLX: {gl["x"]} GLY: {gl["y"]} VS X: {location["x"]} Y: {location["y"]}')
        raise NotImplementedError

    def get_source_id(self, _from, container=False):
        """
        when container=True => we move into  grid, so we don't need to find what is there
        """
        if 'container' in _from:
            parent_pid = _from['container']['parent_id']
            if container:
                return parent_pid

            parent = self.all_items[parent_pid]
            if 'location_in_grid' not in _from:
                return _from['container']['parent_id']

            location = _from['location_in_grid']
            _from_pid = self.get_pid_in_grid(parent, location)

        elif 'owner_container' in _from:
            _from_pid = _from['owner_container']['parent_id']
        else:
            pprint(_from)
            # exit(131)
        return _from_pid

    def grid_add(self, item, container, location):
        for grid in container['grid']:
            grid['items'].append({'item': item, 'location': location})
            return

    def process_move(self, move_operation):
        _from = move_operation['from']
        _to = move_operation['to']
        if 'stub' in _from or 'stub' in _to:
            return
        # print(f'Move {_from} => {_to}')
        _from_pid = self.get_source_id(_from)
        _to_pid = self.get_source_id(_to, container=True)

        # from_item = self.all_items[_from_pid]
        from_item = self.all_items[move_operation['id']]
        from_parent_key = from_item['parent']
        if isinstance(from_parent_key, str):
            from_parent = self.all_items[from_item['parent']]
        else:
            from_parent = from_item

        to_item = self.all_items[_to_pid]
        to_parent_key = to_item['parent']
        if isinstance(to_parent_key, str):
            to_parent = self.all_items[to_item['parent']]
        else:
            to_parent = to_item

        # print(f'Move {_from} => {_to}')
        # print('FROM:')
        # pprint(from_item)
        # print('from parent')
        # pprint(from_parent)
        # print('TO:')
        # pprint(to_item)
        # print('to parent')
        # pprint(to_parent)

        old_price = get_total_price(from_parent)
        update_crates = []

        if from_item['id'] == from_parent['id']:
            if 'crate' in from_item:
                crate = from_item['crate']
                crate['item'] = {'info': {'price': 0}, 'id': 'deleted_item', 'stack_count': 0}
                self.hide(crate['id'])
        else:
            recurse_delete(from_parent, from_item['id'])

        if 'location_in_grid' in _to:  # move into grid
            self.grid_add(from_item, to_item, _to['location_in_grid'])
        elif 'container' in _to:  # equipping
            ppid = _to['container']['parent_id']

            to_parent = self.all_items[ppid]
            to_parent['slots'].append(
                {'contained_item': from_item, 'id': _to['container']['container_id']}
            )
        if 'player' in to_parent:
            pass

        if 'crate' in from_item:
            del from_item['crate']
        elif 'player' in from_item:
            del from_item['player']
        else:
            raise NotImplementedError

        if 'crate' in to_parent:
            from_item['crate'] = to_parent['crate']
        elif 'player' in to_parent:
            from_item['player'] = to_parent['player']
        else:
            raise NotImplementedError

        self.update_crate_or_player(from_parent, from_item)
        self.update_crate_or_player(to_parent, from_item)

    def process_split(self, split_operation):
        # print(f'Split operation: {split_operation}')
        # pprint(self.all_items[split_operation['id']])
        assert split_operation['count'] < 210_000
        # raise NotImplementedError

    def update_crate_or_player(self, src, item):
        if 'player' in src:
            src['player'].update_loot_price()

        elif 'crate' in src:
            crate = src['crate']
            new_price = get_total_price(crate['item'])

            if crate.get('ephemeral', False):
                self.hide(crate['id'])
                new_price = 0
            crate['total_price'] = new_price
            if new_price < self.PRICE_TRESHOLD:
                self.hide(src['crate']['id'])
            else:
                self.unhide(src['crate']['id'])
            # print(f'OLD: {old_price} => {new_price}')

    def update_by_price(self):
        self.by_price = sorted(self.by_id.values(), key=lambda x: -x.get('total_price', 0))

    def should_update_location(self):
        me = GLOBAL['me']
        if not me:
            return False
        delta = dist(me.pos, self.last_pos)
        if delta > 0.1 or self.skipped_updates > 2:
            self.last_pos = me.pos.copy()
            return me

    @property
    def overloaded(self):
        return GLOBAL['get_qsize']() > 2000

    def update_location(self):
        me = self.should_update_location()
        if not me:
            self.skipped_updates += 1
            return
        self.skipped_updates = 0

        t = time.time()
        if self.overloaded and self.hard_skips < 50 and t - self.last_update < 5:
            rows = self.display_rows()
            self.hard_skips += 1
        else:
            rows = self.by_id.values()
            self.hard_skips = 0
            self.last_update = t

        for item in rows:
            item_pos = item['position']
            item['dist'] = round(dist(me.pos, item_pos), 1)
            item['angle'] = angle_from_me(me, item_pos)
            item['vdist'] = round(item_pos[1] - me.pos[1], 1)
        self.update_by_dist()

    PRICE_TRESHOLD = 18000
    IGNORE = ['quest_']
    # IGNORE = []

    def is_ignored(self, item):
        name = item.get('name', 'NO NAME')
        for i in self.IGNORE:
            if name.startswith(i):
                return True

    def get_loot(self, items, num, classes=[]):
        out = []
        # remove quest_
        for item in items:
            if not isinstance(item, dict):
                continue
            if item['id'] in self.added:
                continue

            if self.is_ignored(item):
                continue
            if not classes:
                self.added.append(item['id'])
                if 'wanted' in item:
                    out.append({'item': item, 'classes': ['wanted']})
                else:
                    out.append(item)
            else:
                self.added.append(item['id'])
                out.append({'item': item, 'classes': classes})
            if len(out) >= num:
                break
        return out

    def update_by_dist(self):
        self.by_dist = sorted(self.by_id.values(), key=lambda x: x.get('dist', 1000.0))
        self.by_dist_wanted = sorted(self.wanted.values(), key=lambda x: x.get('dist', 1000.0))

    def item_to_row(self, item):
        classes = ['loot']
        if 'classes' in item:
            classes.extend(item['classes'])
            item = item['item']

        if 'name' in item:
            name = item['name']
        else:
            item['name'] = f"NO NAME: {item['item']['template_id']}"
            name = item['name']
        # name = item.get('name', 'NO NAME')
        # if name == 'quest_sas_san1':
        #     pprint(item)
        dist = item.get('dist', '-')

        if isinstance(dist, float):
            if dist < 50:
                classes.append('nearby')

        return {
            'className': ' '.join(classes),
            'row': [
                dist,
                item.get('vdist', '-'),
                item.get('angle', '-'),
                {
                    'text': name,
                    'action': {
                        'type': 'MSG_TO_SERVER',
                        'payload': {'type': 'LOOT_HIDE', 'payload': {'id': item['id']}},
                    },
                },
                f'Price: {item.get("total_price", "unk")}',
                {
                    'text': 'disable',
                    'action': {
                        'type': 'MSG_TO_SERVER',
                        'payload': {'type': 'LOOT_HIDE', 'payload': {'id': item['id']}},
                    },
                },
            ],
        }

    def display_rows(self):
        me = GLOBAL['me']
        self.added = []

        if not me:
            return []

        if not self.by_dist:
            return []
        rows = self.get_loot(self.by_dist, self.BY_DIST_NEARBY)

        if self.wanted:
            rows.extend(self.get_loot(self.by_dist_wanted, self.BY_DIST_WANTED, classes=['wanted']))
        if self.by_price:
            rows.extend(self.get_loot(self.by_price, self.BY_PRICE_EXPENSIVE))
        return rows

    def loot_to_json(self, item):
        if 'name' in item:
            name = item['name']
        else:
            item['name'] = f"NO NAME: {item['item']['template_id']}"
            name = item['name']

        return {
            'type': 'loot',
            'id': item['id'],
            'name': name,
            'dist': item.get('dist', 1000.0),
            'vdist': item.get('vdist', 1000.0),
            'angle': item.get('angle', 1000.0),
            'total_price': item.get('total_price', 'unk'),
            'wanted': item.get('wanted', False),
            'action': {
                'type': 'MSG_TO_SERVER',
                'payload': {'type': 'LOOT_HIDE', 'payload': {'id': item['id']}},
            },
        }

    def display_loot(self):
        """ dist, vdist, angle, name, coord, is_alive """
        self.display_rows()
        return [self.loot_to_json(item) for item in self.by_id.values()]
        rows = self.display_rows()

        return [self.item_to_row(item) for item in rows]


def angle_from_me(player, dst):
    return angle(player.pos, dst, player.rot)


GLOBAL = {
    'map': None,
    'me': None,
    'loot': Loot(),
    'get_qsize': lambda: random.randint(1, 100),
    'on_exit': [],
}
PLAYERS = {}


def clear_global():
    GLOBAL['map'] = None
    GLOBAL['me'] = None
    GLOBAL['loot'] = Loot()
    PLAYERS.clear()


class ParsingMethods:
    def read_size_and_bytes(self, data=None):
        if data is None:
            data = self.data
        size = data.read_u16()
        return data.read_bytes(size)

    def read_rot(self):
        return {
            "x": self.data.read_f32(),
            "y": self.data.read_f32(),
            "z": self.data.read_f32(),
            "w": self.data.read_f32(),
        }

    def read_pos(self):
        return np.array([self.data.read_f32(), self.data.read_f32(), self.data.read_f32()])


class Map(ParsingMethods):
    log = logging.getLogger('Map')

    def zjson(self, what):
        return json.loads(zlib.decompress(what))

    def __init__(self, msg):
        self.msg = msg
        self.data = msg.data

        unk = self.data.read_u8()  # byte_0

        real_dt = 0 if self.data.read_u8() else self.data.read_u64()
        game_dt = self.data.read_u64()
        # print(f'Real DT: {real_dt} Game DT: {game_dt}')
        time_factor = self.data.read_f32()

        unk1 = self.read_size_and_bytes()  # assets / json
        unk2 = self.read_size_and_bytes()  # some ids

        unk3 = self.read_size_and_bytes()  # weather?

        unk4 = self.data.read_u8()  # bool_8
        member_type = self.data.read_u32()
        unk5 = self.data.read_f32()
        unk6 = self.read_size_and_bytes()  # lootables?
        unk7 = self.read_size_and_bytes()
        self.bound_min = self.read_pos()
        self.bound_max = self.read_pos()
        unk8 = self.data.read_u16()
        unk9 = self.data.read_u8()
        self.log.warning(f"Map: {self.bound_min} to {self.bound_max}")
        self.exits = {}

    @property
    def bb(self):
        return self.bound_min, self.bound_max

    def set_exits(self, exits: dict):
        self.exits = exits


class Player(ParsingMethods):
    log = logging.getLogger('Player')

    def __init__(self, msg: MsgDecoder, me=False):
        self.me = me
        self.price = 0
        self.loot_price = 0
        self.price_class = '-1'
        self.is_scav = False
        self.group_id = -1

        if not msg:
            return

        if me:
            GLOBAL['me'] = self

        self.msg = msg
        self.data = msg.data

        self.spawn_time = time.time()

        self.pid = self.data.read_u32()
        self.cid = self.data.read_u8()
        self.pos = self.read_pos()
        self.deserialize_initial_state()
        PLAYERS[self.cid] = self
        self.__cached_name = self.get_name()
        self.log = logging.getLogger(f'{self}')

    def update_loot_price(self):
        _my_total_price = 0
        SKIP = ['SecuredContainer', 'Scabbard']

        def tot(item, nesting, ctx):
            nonlocal _my_total_price
            if nesting == 1 and ctx.get('slot', {}).get('id', None) in SKIP:
                return True  # skip

            if isinstance(item, list):
                return
            _my_total_price += item['info'].get('price', 0) * item['stack_count']

        recurse_item(self.inventory, tot)
        self.loot_price = _my_total_price
        self.update_price_class()

    def deserialize_initial_state(self):
        unk2 = self.data.read_u8()
        self.is_alive = self.data.read_u8() == 1
        self.pos = self.read_pos()
        self.rot = quaternion_to_euler(**self.read_rot())
        in_prone = self.data.read_u8() == 1
        self.pose = self.data.read_f32()

        inv_bin = self.read_size_and_bytes()
        try:
            top_ctx = {'total_price': 0}
            ctx = {'top': top_ctx}
            self.inventory = read_item(ByteStream(inv_bin), ctx=ctx)
            self.inventory['player'] = self
            GLOBAL['loot'].store_item(self.inventory, {'player': self})
        except:
            self.log.exception('During decode')
            if self.msg.transport.replay:
                print('exit 112')
                exit(112)

        # print(f'TP: {ctx}')
        self.price = top_ctx['total_price']
        self.update_loot_price()

        prof_zip = self.read_size_and_bytes()
        self.prof = json.loads(zlib.decompress(prof_zip))
        self.full_prof = copy.copy(self.prof)

        self.prof.pop("Encyclopedia")
        self.prof.pop("BackendCounters")
        self.prof.pop("Bonuses")
        self.prof.pop("Skills")
        self.prof.pop("Quests")
        self.prof.pop("InsuredItems")
        self.prof.pop("ConditionCounters")
        self.prof.pop("Stats")

        self.log.debug(self.prof)
        info = self.prof.get("Info")
        self.nickname = info.get("Nickname")
        self.lvl = info.get("Level")
        self.surv_class = self.prof.get("SurvivorClass")
        self.is_scav = info.get("Side") == "Savage"
        self.is_npc = self.is_scav and self.prof.get('aid') == '0'
        side = info.get("Side")
        self.side = "SCAV" if side == "Savage" else side
        self.group_id = info.get('GroupId', None)
        if self.group_id:
            self.group_id = self.group_id
        self.log.info(
            f"OBS POS:{self.nickname} => {self.pos} ROT: {self.rot} Prone: {in_prone} POSE: {self.pose}"
        )

    def update_price_class(self):
        if self.loot_price < 10000:
            self.price_class = '<10k'
            self.price_class = f'{self.loot_price}Rub'
        elif self.loot_price < 1000_000:
            self.price_class = f'{self.loot_price // 1000}K'
        else:
            self.price_class = f'{round(self.loot_price / 1000_000, 1)}M'

    def get_name(self):
        return (
            f'[{"BOT" if self.is_npc else self.lvl}/{self.side}/'
            f'{self.surv_class[:4]}/{self.group_id and self.group_id[-3:]}] {self.nickname}:'
            f'{self.price_class}[{self.cid}]'
        )

    def __str__(self):
        return self.__cached_name

    @staticmethod
    def dummy(cid, me=False):
        log.debug(f'Create dummy player: {me} / {cid}')
        player = Player(msg=None, me=me)
        player.cid = cid
        player.lvl = -1
        player.side = f'UNK'
        player.nickname = f'Unk:me={me}'
        player.is_npc = False
        player.surv_class = 'UNK'
        player.is_alive = True
        player.pos = np.array([0, 0, 0], np.float)
        player.rot = np.array([0, 0, 0], np.float)
        PLAYERS[cid] = player
        player.__cached_name = player.get_name()
        return player

    @property
    def rnd_pos(self):
        return {
            'x': round(self.pos[0], 1),
            'y': round(self.pos[1], 1),
            'z': round(self.pos[2], 1),
        }

    def angle(self):
        me = GLOBAL['me']
        if not me:
            return 0
        if self.me:
            ret = -int(norm_angle(self.rot[0] + 90))
            return f'{ret}/{int(self.rot[0])}'
        me = GLOBAL['me']
        return angle(me.pos, self.pos, me.rot)

    @property
    def yaw(self):
        return self.rot['x']

    @property
    def pitch(self):
        return self.rot['y']

    @property
    def fwd_vector(self):
        vec = fwd_vector(self.pitch, self.yaw, self.pos)
        return vec

    def dist(self):
        me = GLOBAL['me']
        if not me:
            return 0
        return round(dist(self.pos, me.pos), 1)

    def vdist(self):
        me = GLOBAL['me']
        if not me:
            return 0
        if self.me:
            return GLOBAL['get_qsize']()
        return round(self.pos[1] - me.pos[1], 1)

    def print(self, msg, *args, **kwargs):
        if True or self.nickname.startswith("Гога"):
            self.log.info(msg, *args, **kwargs)

    def update(self, msg, data):
        self.msg = msg  # type: MsgDecoder
        self.data = data  # type: BitStream
        if self.me:
            self.log.debug(f"Skip myself {self}")
            return
        args = {"min_value": 1, "max_value": 5}
        if self.data.read_bits(1) == 0:
            args = {"min_value": 0, "max_value": 2097151}
            # args = {'max_value': 1037149}  # < 20 bit
        num = self.data.read_limited_bits(**args)

        game_time = self.data.read_f32()
        # print(f'Time: {game_time}')
        is_disconnected = self.data.read_bits(1)
        self.data.read_check(299)
        self.log.debug(f"OFFST: {self.data.bit_offset}")
        is_alive = self.data.read_bits(1)

        ctx = self.msg.ctx
        curr_packet = self.msg.transport.curr_packet
        msg_det = f'PCKT: {curr_packet["num"]}/{curr_packet["len"]} CID: {ctx["channel_id"]}'
        self.log.debug(
            f'Num is {num} GT: {game_time} Disc: {is_disconnected} IsALIVE: {is_alive}'
            f' {self} {msg_det} Len: {len(self.data.orig_stream)}'
        )
        # self.log.debug(self.data.orig_stream)
        # self.log.warning(f'IS ALIVE: {is_alive}')
        if not is_alive:
            # probably not died but not alive yet
            self.is_alive = False
            inv_hash = self.data.read_u32()
            time = self.data.read_u64()
            # self.data.align()
            # print(f'{hex(self.data.read_bits(16))}:')
            nickname = self.data.read_string(1350)
            side = self.data.read_u32()
            status = self.data.read_string(1350)
            killer = self.data.read_string(1350)
            lvl = self.data.read_u32()
            weapon = self.data.read_string()
            self.log.debug(f'{nickname} {status} {killer} with {weapon}. Msg in: {self}')
        else:
            self.data.read_check(304)
            self.update_position()
            self.update_rotation()
            self.skip_misc()
            try:
                self.update_loot()
            except:
                self.log.exception(f'When update loot: incoming={self.msg.incoming}')
                # old = self.data.bit_offset
                # self.data.bit_offset = 0
                # size = len(self.data.orig_stream)
                # print(self.data.orig_stream)
                # print(f'Size: {size} HX: {hex(size)}')
                # ByteStream(self.data.orig_stream).dump_to('error.bin')
                # ByteStream(self.msg.curr_packet['data']).dump_to('to_test.bin')
                # exit(134)  # TODO: delme
                pass

    def update_me(self, msg: MsgDecoder, data: BitStream):
        self.msg = msg
        self.data = data
        num = self.data.read_limited_bits(0, 127)
        self.log.debug(f'NUM: {num}')
        for i in range(num):
            if self.data.read_bits(1):
                rtt = self.data.read_u16()
            else:
                rtt = 0
            dt = self.data.read_limited_float(0.0, 1.0, 0.0009765625)
            frame = self.data.read_limited_bits(0, 2097151)
            if self.data.read_bits(1):
                frame2 = self.data.read_limited_bits(0, 2097151)
            else:
                frame2 = self.data.read_limited_bits(0, 15)
            # self.data.read_bits(20)
            self.log.debug(f'DT: {dt}/ {rtt} /F1: {frame} {frame2}.  {self.msg}')
            # self.data.bit_offset -= 3
            if self.update_position():
                self.update_rotation()
                self.skip_misc()
                self.update_loot()
                # GLOBAL['loot'].update_location()   # TODO: delme

    def skip_misc(self):
        d: BitStream = self.data
        start_bit = d.bit_offset  # TODO: delme
        # print(f'IS ALIGNED: {d.aligned}')
        d.read_bits()  # sync pos applied

        if d.read_bits():
            d.read_u8()  # command mask

        if d.read_bits():
            eplayer = d.read_limited_bits(0, 31)  # eplayer state

        if d.read_bits():
            animator = d.read_limited_bits(0, 63)  # animator state index

        if d.read_bits():  # movement direction
            d.read_limited_float(-1, 1, 0.03125)
            d.read_limited_float(-1, 1, 0.03125)

        if d.read_bits():  # pose level
            self.pose = d.read_limited_float(0.0, 1.0, 0.0078125)
            # self.pose = d.read_bits(7) # TODO: delme

        if d.read_bits():  # move speed
            d.read_limited_float(0, 1, 0.0078125)

        if d.read_bits():  # tilt
            self.tilt = d.read_limited_float(-5, 5, 0.0078125)
            # self.tilt = d.read_bits(7)

        if d.read_bits():
            if not d.read_bits():  # movements step
                d.read_bits()

        d.read_check()
        blind_fire = d.read_limited_bits(-1, 1)  # blind fire
        soft_surface = d.read_bits()  # soft surface

        if not d.read_bits():  # head rotation
            d.read_limited_float(-50, 50, 0.0625)
            d.read_limited_float(-50, 50, 0.0625)

        d.read_bits()  # no stamina, no oxy, no hands stamina
        d.read_bits()
        d.read_bits()
        d.read_check()

        if d.read_bits():
            if d.read_bits():  # door
                if d.read_bits():
                    _type = d.read_limited_bits(0, 4)
                    d.read_string(1350)
                    d.read_limited_bits(0, 2)
                    if _type == 2:
                        d.read_limited_string(' ', 'z')

            if d.read_bits():  # loot interaction
                if d.read_bits():
                    loot_id = d.read_string(1350)
                    callback_id = d.read_u32()

            if d.read_bits():  # stationary weapon
                if d.read_bits():
                    _type = d.read_u8()
                    if _type == 0:
                        d.read_string()
            if d.read_bits():  # plant item
                if d.read_bits():
                    d.read_string()
                    d.read_string()

        d.read_check()
        if not d.read_bits():
            optype = d.read_limited_bits(0, 10)
            d.read_limited_string(' ', 'z')
            d.read_limited_bits(0, 2047)
            if optype == 6:
                d.read_limited_bits(0, 7)
                d.read_f32()
            d.read_limited_bits(-1, 3)
        self.log.info(f'SKIP BITS FROM {start_bit} to {d.bit_offset}')  # TODO: delme

    def read_one_loot(self):
        d: BitStream = self.data
        # d.bit_offset -= 3
        if d.read_bits():
            size = d.read_bits(16)
            data = d.read_bytes_aligned(size)
            cb = d.read_limited_bits(0, 2047)
            hash = d.read_u32()
            data = ByteStream(data)

            poly = read_polymorph(data, {}, reraise=True)
            if poly:
                try:
                    if 'move_operation_id' in poly:
                        GLOBAL['loot'].process_move(poly)
                    elif 'split_operation_id' in poly:
                        GLOBAL['loot'].process_split(poly)
                except:
                    self.log.exception(f'Process operation: {poly}')
                    # exit(133)  # TODO: delme

    def update_loot(self):
        self.log.info(
            f'Loot position: {self.data.bit_offset} / {self.data.bit_offset / 8}'
        )  # TODO: delme
        # self.data.align()
        # self.data.print_rest()
        d: BitStream = self.data
        num = d.read_u8()
        for i in range(num):
            if not self.msg.incoming:
                self.read_one_loot()
                continue
            tag = d.read_u8()
            if tag == 1:  # command
                self.read_one_loot()
                continue
            # deserialize status
            _id = d.read_bits(16)
            status = d.read_limited_bits(0, 3)
            if status == 2:
                d.read_limited_string(' ', '\x7f')
            if d.read_bits():
                d.read_u32()
                d.read_bits()

    exit = math.inf

    def update_position(self, check=True):
        # assert self.is_alive
        last_pos = copy.copy(self.pos)
        self.data.read_check()
        read = self.data.read_bits(1) == 1
        if read:
            # self.log.debug(f"Update position {self} Read: {read} ME: {self.me}")
            partial = self.data.read_bits(1) == 1
            if partial:
                q_x = FloatQuantizer(-1, 1, Q_LOW)
                q_y = FloatQuantizer(-1, 1, Q_HIGH)
                q_z = FloatQuantizer(-1, 1, Q_LOW)
            else:
                curr_map = GLOBAL["map"]  # type: Map
                if not curr_map:
                    return
                _min = curr_map.bound_min
                _max = curr_map.bound_max
                q_x = FloatQuantizer(_min[0], _max[0], Q_LOW)
                q_y = FloatQuantizer(_min[1], _max[1], Q_HIGH)
                q_z = FloatQuantizer(_min[2], _max[2], Q_LOW)
            dx = q_x.read(self.data)
            dy = q_y.read(self.data)
            dz = q_z.read(self.data)
            self.log.debug(f'DX: {dx} DY: {dy} DZ: {dz}')

            if partial:
                self.pos += np.array([dx, dy, dz])
            else:
                self.pos = np.array([dx, dy, dz])

            # self.log.debug(
            #     f"Moved: {last_pos} => {self.pos} PARTIAL: {partial}"
            # )
            if check and False:
                bb_min, bb_max = GLOBAL["map"].bb
                if not (bb_min["y"] <= self.pos["y"] <= bb_max["y"]):
                    self.log.debug(f'BB IS: {GLOBAL["map"].bb}')
                    self.data.reset()
                    self.log.debug(f'{bytes(self.data.rest)}')
                    print('Exit 111')
                    exit(111)
                assert bb_min["x"] <= self.pos["x"] <= bb_max["x"]
                assert bb_min["y"] <= self.pos["y"] <= bb_max["y"]
                assert bb_min["z"] <= self.pos["z"] <= bb_max["z"]
        else:
            self.log.debug(f"Rest is: {self.data.bit_offset} Size: {len(self.data.stream)}")
        return True

    def update_rotation(self):
        if self.data.read_bits():
            qx = FloatQuantizer(0.0, 360.0, 0.015625)
            qy = FloatQuantizer(-90.0, 90.0, 0.015625)
            #        before = copy.copy(self.rot)
            x = qx.read(self.data)
            y = qy.read(self.data)
            self.rot[0] = min(360.0, x)
            self.rot[1] = y
            # if self.me:
            #     print(f'Rotated: {self.fwd_vector}')


class MsgDecoder(ParsingMethods):
    log = logging.getLogger("MsgDecoder")

    def __init__(self, transport: NetworkTransport, ctx: dict):
        self.transport = transport
        self.curr_packet = transport.curr_packet
        self.ctx = ctx
        self.incoming = ctx["incoming"]
        self.channel_id = ctx["channel_id"]
        self.decoded = False

    @property
    def packet_num(self):
        return self.curr_packet["num"]

    def __str__(self):
        return f'<MSG:{self.op_type} MLEN: {self.len} PKT:{self.curr_packet["num"]}/{self.curr_packet["len"]}>'

    def parse(self, stream):
        # print('parse in MsgDecoder')
        # bprint(stream)
        msg = {}
        self.len, stream = split_16le(stream)
        self.op_type, stream = split_16le(stream)
        # _, stream = split_8(stream)
        self.content, stream = split(stream, self.len)

        # n = self.curr_packet['num']
        # from_ = 200
        # to_ = from_ + 200
        # if from_ < n < to_:
        #     print(f'Num: {n} OP: {self.op_type}')
        #     pprint(self.content)
        # elif n > to_:
        #     import sys
        #     sys.exit(1)

        self.log.debug(f'M: {self}')
        # stream.print_rest()
        self.try_decode()
        # print(msg)
        # print(f'return offset: {stream.bit_offset} / {len(stream.stream)}')
        return stream

    exit = 1

    def init_server(self):
        if not self.ctx["incoming"]:
            return
        try:
            self.data.read_u8()  # encrypted flag?
            curr_map = Map(self)
        except:
            self.log.exception('AAA')
            ByteStream(self.curr_packet['data']).dump_to('error.bin')
            exit(0)
        GLOBAL["map"] = curr_map

    def decode(self):
        self.data = ByteStream(self.content)

        if self.op_type == SERVER_INIT:
            self.init_server()
        elif self.op_type == BATTLE_EYE:
            return
        elif self.op_type == SUBWORLD_SPAWN:
            self.process_subworld_spawn(self.data)
        elif self.op_type == PLAYER_SPAWN:
            self.player = Player(self, me=True)
        elif self.op_type == OBSERVER_SPAWN:
            self.player = Player(self)
        elif self.op_type == OBSERVER_UNSPAWN:
            self.pid = self.data.read_u32()
            self.cid = self.data.read_u8()
            print(f"Exit: {PLAYERS[self.cid]}")
            del PLAYERS[self.cid]
        elif self.op_type == GAME_UPDATE:
            # print(f'READSIZE: {len(self.content)} / {self.content} / {self}')
            # bprint(self.content)
            up_bin = self.read_size_and_bytes()
            up_data = BitStream(up_bin)
            # print(f'UP_DATA: {str(up_data.stream)} / {up_data.orig_stream}')
            if not self.ctx["incoming"]:
                self.update_outbound(up_data)

            elif up_data.read_bits(1) == 1:
                self.update_player(up_data)
            else:
                if not self.ctx["incoming"]:
                    print(self.transport.curr_packet)
                    print("Exit 22")
                    exit(22)
                self.update_world(up_data)
        elif self.op_type == WORLD_SPAWN:
            self.process_world_spawn(self.data)
        else:
            self.log.warning(f'Cannot process: {self}')

        if MsgDecoder.exit <= 0:
            print("Exit 20")
            exit(20)

    def process_world_spawn(self, data: ByteStream):
        exits = {}
        try:
            num = data.read_u16()
            for i in range(num):
                nl = data.read_u16()
                name = ''.join(chr(data.read_u8()) for c in range(nl))
                status = data.read_u8()
                skip = data.read_bytes(6)
                exits[name] = status

        except:
            self.log.exception('AAA')
        GLOBAL['map'].set_exits(exits)

    def process_subworld_spawn(self, data: ByteStream):
        if not data.read_bytes(1):
            return
        loot_json = self.read_size_and_bytes(data)
        loot_info = self.read_size_and_bytes(data)
        d = ByteStream(zlib.decompress(loot_json))
        out = read_many_polymorph(d)
        GLOBAL['loot'].add_loot(self, out)

    def update_player(self, up_data: BitStream):
        # get by `channel_id` or `channel_id - 1`
        player = PLAYERS.get(
            self.channel_id, PLAYERS.get(self.channel_id - 1, None)
        )  # type: Player

        # player = PLAYERS.get(self.channel_id, None)  # type: Player
        if not player and self.channel_id % 2 == 1:
            player = Player.dummy(self.channel_id)

        self.log.debug(f"Update player: {player}")
        player.update(self, up_data)

    def update_outbound(self, up_data: BitStream):
        # if self.curr_packet['num'] == 1433:
        #     self.log.debug(f'{bytes(up_data.rest)}')
        #     exit(112)
        if not GLOBAL['me']:
            GLOBAL['me'] = Player.dummy(self.channel_id, me=True)
        GLOBAL['me'].update_me(self, up_data)

    def update_world(self, up_data: BitStream):
        return
        up_data.read_bits(4)  # skip
        if up_data.read_bits(1):  # loot sync
            num = up_data.read_limited_bits(1, 64)
            for i in range(num):
                _id = up_data.read_u32()
                if up_data.read_bits(1):
                    pass

    def try_decode(self):
        t = time.time()
        try:
            self.decode()
            self.decoded = True
        except Exception as e:
            self.log.exception(f"While decode packet. Incoming={self.ctx['incoming']}")
            # ByteStream(self.curr_packet['data']).dump_to('error.bin')
            # BitStream.DEBUG = True
            # be = BitStream(self.content).stream_be
            # print(be)
            # print(self.content)
            # print(f'SDLEN: {len(BitStream(self.content).stream_be)}')
            # print(f'LEN: {len(self.content)} HX: {hex(len(self.content))}')
            # exit(0)
        finally:
            d = time.time() - t
            if d > 1:
                self.log.warning(f'Heavy msg: {d:.3} {self}')
