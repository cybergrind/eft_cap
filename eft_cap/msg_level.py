import copy
import logging
import math
from array import array
import itertools
import struct
import zlib
import json
from pprint import pprint
import time

from eft_cap import bprint, ParsingError



SERVER_INIT = 147
WORLD_SPAWN = 151
WORLD_UNSPAWN = 152
SUBWORLD_SPAWN = 153
SUBWORLD_UNSPAWN = 154
PLAYER_SPAWN = 155
PLAYER_UNSPAWN = 156
OBSERVER_SPAWN = 157
OBSERVER_UNSPAWN = 158
BATTL_EEYE = 168
GAME_UPDATE = 170


def bits_required(min_value, max_value):
    assert max_value > min_value

    return math.ceil(
        math.log2(max_value - min_value)
    )


class FloatQuantizer:
    def __init__(self, min_value, max_value, resolution):
        self.min_value = min_value
        self.max_value = max_value
        self.resolution = resolution
        self.delta = self.max_value - self.min_value
        self.max_int = math.ceil((self.max_value - self.min_value) / self.resolution)
        self.bits_require = bits_required(0, self.max_int)

    def bits_require(self):
        return bits_required(0, self.max_int)

    def dequantize_float(self, int_value):
        return int_value / float(self.max_int) * self.delta + self.min_value


def decode_xyz(stream):
    pass


def to_bits(byte):
    assert byte < 256
    bits = bin(byte)[2:]
    out = []
    for i in range(8 - len(bits)):
        out.append(0)
    for bit in bits:
        out.append(int(bit))
    assert len(out) == 8
    return out


def to_byte(bits):
    # big endian bits
    assert len(bits) == 8, bits
    out = 0
    for i in range(8):
        out += bits[i] << 7 - i
    return out


class Stream:
    def __init__(self, stream):
        self.bit_offset = 0
        self.orig_stream = stream
        bitstring = itertools.chain.from_iterable([to_bits(one_byte) for one_byte in stream])
        self.stream = array('B', bitstring)

    @property
    def rest(self):
        assert len(self.stream[self.bit_offset:]) % 8 == 0, f'Off: {self.bit_offset}'
        bytes_list = []
        i = self.bit_offset
        while i < len(self.stream):
            idx = i
            bytes_list.append(to_byte(self.stream[idx:idx + 8]))
            i += 8
        return bytes(bytes_list)

    def print_rest(self):
        bit = self.bit_offset
        bprint(self.rest)
        self.bit_offset = bit

    def read_l_bits(self, bits):
        """
        little endian bits
        """
        assert bits <= 8
        out = 0
        for i in range(bits):
            # out += self.stream[self.bit_offset] << i  # reversed order
            shift = bits - 1 - i
            # shift = i
            num = self.stream[self.bit_offset] << shift
            # print(f'Shift => {shift} : Num: {num}')
            out += num
            self.bit_offset += 1
        return out

    def read_bits(self, bits):
        if bits <= 8:
            return self.read_l_bits(bits)
        else:
            acc = 0
            for i in range(bits // 8):
                acc += self.read_l_bits(8)
            acc += self.read_l_bits(bits % 8)
            return acc

    def read_limited_bits(self, min_value=0, max_value=1):
        required = bits_required(min_value, max_value)
        return self.read_bits(required) + min_value

    def read_bytes(self, num_bytes):
        required = num_bytes * 8
        remains = len(self.stream) - self.bit_offset
        if required > remains:
            self.print_rest()
            print(f'Read: {num_bytes}')
            raise ParsingError(f'Need: {required} Remains: {remains} Offset: {self.bit_offset}')
        assert self.bit_offset % 8 == 0
        boff = int(self.bit_offset / 8)
        # print(f'Get bytes: {num_bytes} BOFF: {boff} OFF: {boff + num_bytes}')
        resp = self.orig_stream[boff:(boff + num_bytes)]
        self.bit_offset += num_bytes * 8
        return resp

    def read_u8(self):
        return self.read_bits(8)

    def read_u16(self):
        b1 = self.read_bits(8)
        b2 = self.read_bits(8) << 8
        # print(f'B1: {b1} B2: {b2}')
        return b1 + b2

    def read_u32(self):
        return (
            self.read_bits(8) +
            self.read_bits(8) << 8 +
            self.read_bits(8) << 16 +
            self.read_bits(8) << 24
        )

    def read_u64(self):
        return struct.unpack('<Q', self.read_bytes(8))[0]

    def read_f32(self):
        if self.bit_offset % 8 == 0:
            bf32 = self.read_bytes(4)
        else:
            bf32 = bytes([self.read_bits(8),
                          self.read_bits(8),
                          self.read_bits(8),
                          self.read_bits(8)])
        return struct.unpack('<f', bf32)[0]

    def reset(self):
        self.bit_offset = 0

GLOBAL = {
    'map': None,
}
PLAYERS = {}

class ParsingMethods:
    def read_size_and_bytes(self):
        size = self.data.read_u16()
        return self.data.read_bytes(size)

    def read_rot(self):
        return {
            'a': self.data.read_f32(),
            'b': self.data.read_f32(),
            'c': self.data.read_f32(),
            'd': self.data.read_f32()
        }

    def read_pos(self):
        return {'x': self.data.read_f32(),
                'y': self.data.read_f32(),
                'z': self.data.read_f32()}


class Map(ParsingMethods):
    def __init__(self, msg):
        self.msg = msg
        self.data = msg.data

        unk = self.data.read_u8()
        real_dt = 0 if self.data.read_u8() else self.data.read_u64()
        game_dt = self.data.read_u64()
        # print(f'Real DT: {real_dt} Game DT: {game_dt}')
        time_factor = self.data.read_f32()

        unk1 = self.read_size_and_bytes()  # assets / json
        unk2 = self.read_size_and_bytes()  # some ids
        unk3 = self.read_size_and_bytes()  # weather?
        unk4 = self.data.read_u8()
        member_type = self.data.read_u32()
        unk5 = self.data.read_f32()
        unk6 = self.read_size_and_bytes()  # lootables?
        unk7 = self.read_size_and_bytes()

        self.bound_min = self.read_pos()
        self.bound_max = self.read_pos()
        unk8 = self.data.read_u16()
        unk9 = self.data.read_u8()
        print(f'Map: {self.bound_min} to {self.bound_max}')


class Player(ParsingMethods):
    def __init__(self, msg, me=False):
        self.me = me
        self.died = False
        self.msg = msg
        self.data = msg.data

        self.spawn_time = time.time()

        self.pid = self.data.read_u32()
        self.cid = self.data.read_u8()
        self.pos = self.read_pos()
        self.deserialize_initial_state()
        PLAYERS[self.cid] = self

    def deserialize_initial_state(self):
        unk2 = self.data.read_u8()
        unk3 = self.data.read_u8() == 1
        self.pos = self.read_pos()
        self.rot = self.read_rot()
        in_prone = self.data.read_u8() == 1
        pose_lvl = self.data.read_f32()

        inv_bin = self.read_size_and_bytes()
        prof_zip = self.read_size_and_bytes()
        self.prof = json.loads(zlib.decompress(prof_zip))
        self.full_prof = copy.copy(self.prof)

        self.prof.pop('Encyclopedia')
        self.prof.pop('BackendCounters')
        self.prof.pop('Bonuses')
        self.prof.pop('Skills')
        self.prof.pop('Quests')
        self.prof.pop('InsuredItems')
        self.prof.pop('ConditionCounters')
        self.prof.pop('Stats')
        pprint(self.prof)
        info = self.prof.get('Info')
        self.nickname = info.get('Nickname')
        self.lvl = info.get('Level')
        self.surv_class = self.prof.get('SurvivorClass')
        self.is_scav = info.get('Side') == 'Savage'
        self.side = info.get('Side')

        print(f'OBS POS: {self.pos} ROT: {self.rot} Prone: {in_prone} POSE: {pose_lvl}')

    def __str__(self):
        return f'[{self.lvl}/{self.side}/{self.surv_class[:4]}] {self.nickname}'

    def update(self, msg, data):
        self.msg = msg
        self.data = data
        if self.me:
            print(f'Skip myself {self}')
        args = {'min_value': 1, 'max_value': 5}
        if self.data.read_bits(1) == 0:
            args = {'min_value': 0, 'max_value': 2097151}
        num = self.data.read_limited_bits(**args)
        game_time = self.data.read_f32()
        # print(f'Time: {game_time}')
        is_disconnected = self.data.read_bits(1)

        if self.data.read_bits(1) != 1:
            # probably not died but not alive yet
            # print(f'Died: {self}')
            # self.died = True
            pass
        else:
            self.update_position()

    def update_position(self):
        print(f'Update {self} Incoming: {self.msg.ctx["incoming"]}')
        last_pos = self.pos
        read = self.data.read_bits(1) == 1
        if read:
            partial = self.data.read_bits(1) == 1
            if partial:
                pass
            pass



class MsgDecoder(ParsingMethods):
    log = logging.getLogger('MsgDecoder')

    def __init__(self, transport, ctx):
        self.transport = transport
        self.ctx = ctx
        self.incoming = ctx['incoming']
        self.channel_id = ctx['channel_id']
        self.decoded = False

    def parse(self, stream):
        # print('parse in MsgDecoder')
        # bprint(stream)
        stream = Stream(stream)
        msg = {}
        self.len = msg['len'] = stream.read_u16()
        self.op_type = msg['op_type'] = stream.read_u16()
        # print(f'LEN: {msg["len"]} OP: {self.op_type}')
        # stream.print_rest()
        self.content = msg['content'] = stream.read_bytes(msg['len'])
        self.try_decode()
        # print(msg)
        self.transport.add_msg(self.ctx, self)
        # print(f'return offset: {stream.bit_offset} / {len(stream.stream)}')
        ret = stream.rest
        if len(ret) > 60:
            # print(f'after ret: {ret[:60]} ....')
            pass
        else:
            # print(f'After ret: {ret}')
            pass
        return ret

    exit = 1

    def init_server(self):
        if not self.ctx['incoming']:
            return
        curr_map = Map(self)
        GLOBAL['map'] = curr_map

    def decode(self):
        self.data = Stream(self.content)

        if self.op_type == SERVER_INIT:
            self.init_server()
        elif self.op_type == PLAYER_SPAWN:
            self.player = Player(self, me=True)
        elif self.op_type == OBSERVER_SPAWN:
            self.player = Player(self)
        elif self.op_type == OBSERVER_UNSPAWN:
            self.pid = self.data.read_u32()
            self.cid = self.data.read_u8()
            print(f'Unspawn: {PLAYERS[self.cid]}')
            # MsgDecoder.exit -= 1
        elif self.op_type == GAME_UPDATE:

            up_bin = self.read_size_and_bytes()
            up_data = Stream(up_bin)
            if not self.ctx['incoming']:
                self.update_outbound(up_data)
            elif up_data.read_bits(1) == 1:
                self.update_player(up_data)
            else:
                if not self.ctx['incoming']:
                    print(self.transport.curr_packet)
                    print('Exit 22')
                    exit(22)
                self.update_world(up_data)
        if MsgDecoder.exit <= 0:
            print('Exit 20')
            exit(20)

    skip_unk_player = math.inf
    def update_player(self, up_data):

        # NOT CID: 3924 => 3
        # 4274 => 4
        # 9975 => 4
        # 11481 {559} => 4
        # 19204 {316} => 4
        # 24137 {203} => 4
        if self.channel_id not in PLAYERS:
            if MsgDecoder.skip_unk_player > 0:
                MsgDecoder.skip_unk_player -= 1
                return
            print(f'Players: {list(PLAYERS.keys())} CID: {self.channel_id}')
            print(self.transport.curr_packet)
            print('Exit 21')
            exit(21)
        player = PLAYERS[self.channel_id]
        player.update(self, up_data)
        # MsgDecoder.exit -= 1

    def update_outbound(self, up_data):
        num = up_data.read_limited_bits(0, 127)
        # print(f'Outbound num = {num}')
        return
        for i in range(num):
            rtt = up_data.read_u16() if up_data.read_bits(1) else 0

    def update_world(self, up_data):
        pass


    def try_decode(self):
        try:
            self.decode()
            self.decoded = True
        except Exception as e:
            self.log.exception('While decode packet')
