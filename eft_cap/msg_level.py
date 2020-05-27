from __future__ import annotations

import copy
import itertools
import json
import logging
import math
import struct
import time
import traceback
import zlib
from array import array
from functools import wraps
from pprint import pprint
from typing import TYPE_CHECKING

from eft_cap import ParsingError, bprint, split, split_16le

if TYPE_CHECKING:
    from eft_cap.network_base import NetworkTransport


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


def bin_print(b_str):
    for idx in range(len(b_str)):
        bin_str = bin(b_str[idx])[2:]
        if len(bin_str) < 8:
            bin_str = "".join(["0" for i in range(8 - len(bin_str))]) + bin_str
        print(bin_str, end="\n" if idx % 4 == 3 else " ")


def to_bits(byte):
    # print(f'Convert: {hex(byte)}')
    assert byte < 256
    bits = bin(byte)[2:]
    out = []
    for i in range(8 - len(bits)):
        out.append(0)
    for bit in bits:
        out.append(int(bit))
    assert len(out) == 8
    # print(f'Out => {out}')
    return out


def bin_dump(b_str):
    bitstring = itertools.chain.from_iterable([to_bits(one_byte) for one_byte in b_str])
    with open("bin_dump.bin", "wb") as f:
        f.write(bytes(bitstring))


def bits_required(min_value, max_value):
    assert max_value > min_value
    return math.floor(math.log2(max_value - min_value)) + 1


def dist(a, b):
    return math.sqrt((a['x'] - b['x']) ** 2 + (a['y'] - b['y']) ** 2 + (a['z'] - b['z']) ** 2)


Q_LOW = 0.001953125
Q_HIGH = 0.0009765625


class FloatQuantizer:
    def __init__(self, min_value, max_value, resolution):
        self.min_value = min_value
        self.max_value = max_value
        self.resolution = resolution
        self.delta = self.max_value - self.min_value
        self.max_int = math.ceil((self.max_value - self.min_value) / self.resolution)
        self.bits_require = bits_required(0, self.max_int)

    def dequantize_float(self, int_value):
        return int_value / float(self.max_int) * self.delta + self.min_value

    def read(self, stream):
        return self.dequantize_float(stream.read_bits(self.bits_require))


def decode_xyz(stream):
    pass


def to_byte(bits):
    # big endian bits
    assert len(bits) == 8, bits
    out = 0
    for i in range(8):
        out += bits[i] << 7 - i
    # print(f'Bits {bits} => {out}')
    return out


def bits_to_bytes(bits):
    assert len(bits) % 8 == 0, len(bits)
    out = []
    for i in range(len(bits) // 8):
        out.append(to_byte(bits[i * 8 : i * 8 + 8]))
    return bytes(out)


def euler_to_quaternion(roll, pitch, yaw):
    qx = math.sin(roll / 2) * math.cos(pitch / 2) * math.cos(yaw / 2) - math.cos(
        roll / 2
    ) * math.sin(pitch / 2) * math.sin(yaw / 2)
    qy = math.cos(roll / 2) * math.sin(pitch / 2) * math.cos(yaw / 2) + math.sin(
        roll / 2
    ) * math.cos(pitch / 2) * math.sin(yaw / 2)
    qz = math.cos(roll / 2) * math.cos(pitch / 2) * math.sin(yaw / 2) - math.sin(
        roll / 2
    ) * math.sin(pitch / 2) * math.cos(yaw / 2)
    qw = math.cos(roll / 2) * math.cos(pitch / 2) * math.cos(yaw / 2) + math.sin(
        roll / 2
    ) * math.sin(pitch / 2) * math.sin(yaw / 2)

    return [qx, qy, qz, qw]


def quaternion_to_euler(x, y, z, w):
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll = math.degrees(math.atan2(t0, t1))
    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    pitch = math.degrees(math.asin(t2))
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw = math.degrees(math.atan2(t3, t4))
    return {"x": yaw, "y": pitch, "z": roll}


def packed(fmt, single=True):
    def _wrapped(func):
        @wraps(func)
        def _inner(*args, **kwargs):
            bin_resp = func(*args, **kwargs)
            try:
                unpacked = struct.unpack(fmt, bin_resp)
            except Exception:
                exit(27)
            return unpacked[0] if single else unpacked

        return _inner

    return _wrapped


def stream_from_le(stream, step=4):
    l = len(stream)
    loops = l // step + 0 if l % step == 0 else 1
    for i in range(loops):
        part = stream[i * step : i * step + step]
        part_len = len(part)
        if len(part) == 0:
            return
        if part_len < step:
            part = b"\x00" * (step - part_len) + part
        yield from [b for b in struct.pack(">I", struct.unpack("<I", part)[0])[:part_len]]


class ByteStream:
    log = logging.getLogger("ByteStream")

    def __init__(self, stream):
        self.byte_offset = 0
        self.orig_stream = stream

    def read_bytes(self, num):
        out = self.orig_stream[self.byte_offset : self.byte_offset + num]

        if len(out) != num:
            self.log.error(
                f"OS: {self.orig_stream} OFST: {self.byte_offset} NUM: {num} L: {len(self.orig_stream)}"
            )
            exit(26)
        self.byte_offset += num
        assert len(out) == num
        return out

    def read_u8(self):
        return self.read_bytes(1)[0]

    @packed("<H")
    def read_u16(self):
        return self.read_bytes(2)

    @packed("<I")
    def read_u32(self):
        return self.read_bytes(4)

    @packed("<Q")
    def read_u64(self):
        return self.read_bytes(8)

    @packed("<f")
    def read_f32(self):
        return self.read_bytes(4)


class BitStream:
    log = logging.getLogger("BitStream")

    def __init__(self, stream):
        self.bit_offset = 0
        self.orig_stream = stream
        be_stream = stream_from_le(stream)
        bitstring = itertools.chain.from_iterable([to_bits(one_byte) for one_byte in be_stream])
        self.stream = array("B", bitstring)

    @property
    def rest(self):
        # assert len(self.stream[self.bit_offset:]) % 8 == 0, f'Off: {self.bit_offset}'
        while self.bit_offset <= len(self.stream) - 8:
            yield self.read_bits(8)

    def print_rest(self):
        bit = self.bit_offset
        bprint(self.rest)
        self.bit_offset = bit

    def align(self):
        off = self.bit_offset % 8
        # print(f'Align: -> {off} vs {self.bit_offset}')
        if off:
            self.read_bits(8 - off)
        assert self.bit_offset % 8 == 0

    def read_bits(self, bits):
        bs = self.stream[self.bit_offset : self.bit_offset + bits]
        bs = "".join([str(i) for i in bs])
        if not bs:
            return 0
        self.bit_offset += bits
        # print(f'Eval: 0b{bs}')
        return eval(f"0b{bs}")

    def read_limited_bits(self, min_value=0, max_value=1):
        required = bits_required(min_value, max_value)
        # print(f'Bits: {self.stream[self.bit_offset:self.bit_offset + required]}')
        read = self.read_bits(required)
        ret = read + min_value
        # print(f'Required bits: {required} {read} {ret}')
        return ret

    def read_limited_float(self, min_value=0.0, max_value=1.0, resolution=0.1):
        q = FloatQuantizer(min_value, max_value, resolution)
        return q.read(self)

    def read_bytes(self, num_bytes):

        return bytes([self.read_bits(8) for i in range(num_bytes)])

        required = num_bytes * 8
        remains = len(self.stream) - self.bit_offset
        if required > remains:
            self.log.error(f"Need: {required} Remains: {remains} Offset: {self.bit_offset}")
            try:
                raise Exception
            except Exception as e:
                self.log.exception("ee")
            exit(11)
            raise ParsingError(f"Need: {required} Remains: {remains} Offset: {self.bit_offset}")

        if self.aligned:
            assert self.bit_offset % 8 == 0
            boff = int(self.bit_offset / 8)
            # print(f'Get bytes: {num_bytes} BOFF: {boff} OFF: {boff + num_bytes}')
            resp = self.orig_stream[boff : (boff + num_bytes)]
            self.bit_offset += num_bytes * 8
            return resp
        else:
            return bytes([self.read_bits(8) for i in range(num_bytes)])

    def read_u8(self):
        return self.read_bits(8)

    @packed(">H")
    def read_u16(self):
        return self.read_bytes(2)

    @packed(">I")
    def read_u32(self):
        return self.read_bytes(4)

    @packed(">Q")
    def read_u64(self):
        return self.read_bytes(8)

    @property
    def aligned(self):
        return self.bit_offset % 8 == 0

    @packed(">f")
    def read_f32(self):
        return self.read_bytes(4)

    def read_string(self, max_size=0):
        is_null = self.read_bits(1)
        if is_null:
            return None
        out = []
        self.align()
        num = self.read_u32()
        for i in range(num):
            char = self.read_bytes(2)
            # print(f'Append: {char} LEN: {num}')
            out.extend(char)
        return bytes(out).decode("utf-16-be")

    def reset(self):
        self.bit_offset = 0


GLOBAL = {
    'map': None,
    'me': None,
}
PLAYERS = {}


def clear_global():
    GLOBAL['map'] = None
    GLOBAL['me'] = None
    PLAYERS.clear()


class ParsingMethods:
    def read_size_and_bytes(self):
        size = self.data.read_u16()
        return self.data.read_bytes(size)

    def read_rot(self):
        return {
            "x": self.data.read_f32(),
            "y": self.data.read_f32(),
            "z": self.data.read_f32(),
            "w": self.data.read_f32(),
        }

    def read_pos(self):
        return {
            "x": self.data.read_f32(),
            "y": self.data.read_f32(),
            "z": self.data.read_f32(),
        }


class Map(ParsingMethods):
    log = logging.getLogger('Map')

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
        self.log.info(f"Map: {self.bound_min} to {self.bound_max}")

    @property
    def bb(self):
        return self.bound_min, self.bound_max


class Player(ParsingMethods):
    log = logging.getLogger('Player')

    def __init__(self, msg, me=False):
        self.me = me
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
        self.log = logging.getLogger(f'{self}')

    def deserialize_initial_state(self):
        unk2 = self.data.read_u8()
        self.is_alive = self.data.read_u8() == 1
        self.pos = self.read_pos()
        self.rot = quaternion_to_euler(**self.read_rot())
        in_prone = self.data.read_u8() == 1
        pose_lvl = self.data.read_f32()

        inv_bin = self.read_size_and_bytes()
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
        self.is_npc = self.is_scav and self.lvl == 1
        side = info.get("Side")
        self.side = "SCAV" if side == "Savage" else side

        self.log.info(f"OBS POS: {self.pos} ROT: {self.rot} Prone: {in_prone} POSE: {pose_lvl}")

    def __str__(self):
        return f'[{"BOT" if self.is_npc else self.lvl}/{self.side}/{self.surv_class[:4]}] {self.nickname}[{self.cid}]'

    @property
    def rnd_pos(self):
        return {
            'x': round(self.pos['x'], 2),
            'y': round(self.pos['y'], 2),
            'z': round(self.pos['x'], 2),
        }

    def dist(self):
        return round(dist(self.pos, GLOBAL['me'].pos), 4)

    def vdist(self):
        me = GLOBAL['me']
        return round(self.pos['y'] - me.pos['y'], 3)

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
        if not is_alive:
            # probably not died but not alive yet
            self.log.info(f"Died: {self} Disconnected: {is_disconnected}")
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
            self.log.info(f'{nickname} {status} {killer} with {weapon}. Msg in: {self}')
        else:
            self.update_position()
            self.update_rotation()

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
            self.update_position()
            self.update_rotation()

    exit = math.inf

    def update_position(self, check=True):
        assert self.is_alive
        last_pos = copy.copy(self.pos)
        read = self.data.read_bits(1) == 1
        self.log.debug(f"Update {self} Read: {read} ME: {self.me}")
        if read:
            partial = self.data.read_bits(1) == 1
            if partial:
                q_x = FloatQuantizer(-1, 1, Q_LOW)
                q_y = FloatQuantizer(-1, 1, Q_HIGH)
                q_z = FloatQuantizer(-1, 1, Q_LOW)
            else:
                curr_map = GLOBAL["map"]  # type: Map
                _min = curr_map.bound_min
                _max = curr_map.bound_max
                q_x = FloatQuantizer(_min["x"], _max["x"], Q_LOW)
                q_y = FloatQuantizer(_min["y"], _max["y"], Q_HIGH)
                q_z = FloatQuantizer(_min["z"], _max["z"], Q_LOW)
            dx = q_x.read(self.data)
            dy = q_y.read(self.data)
            dz = q_z.read(self.data)
            self.log.debug(f'DX: {dx} DY: {dy} DZ: {dz}')

            # if self.me and not partial:
            #     exit(102)
            # else:
            #     return

            if partial:
                self.pos["x"] = last_pos["x"] + dx
                self.pos["y"] = last_pos["y"] + dy
                self.pos["z"] = last_pos["z"] + dz
                # self.quant_position()
                pass
            else:
                self.pos["x"] = dx
                self.pos["y"] = dy
                self.pos["z"] = dz

            self.log.debug(
                f"Moved: {last_pos} => {self.pos} {GLOBAL['map'].bb}: PARTIAL: {partial}"
            )
            if check:
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

    def quant_position(self):
        bb_min, bb_max = GLOBAL["map"].bb
        self.pos['x'] = max(bb_min['x'], min(bb_max['x'], self.pos['x']))
        self.pos['y'] = max(bb_min['y'], min(bb_max['y'], self.pos['y']))
        self.pos['z'] = max(bb_min['z'], min(bb_max['z'], self.pos['z']))

    def update_rotation(self):
        if self.data.read_u8():
            qx = FloatQuantizer(0, 360, 0.015625)
            qy = FloatQuantizer(-90, 90, 0.015625)
            before = copy.copy(self.rot)
            self.rot["x"] = qx.read(self.data)
            self.rot["y"] = qy.read(self.data)
            # print(f'Rotated: {before} => {self.rot}')


class MsgDecoder(ParsingMethods):
    log = logging.getLogger("MsgDecoder")

    def __init__(self, transport: NetworkTransport, ctx: dict):
        self.transport = transport
        self.curr_packet = transport.curr_packet
        self.ctx = ctx
        self.incoming = ctx["incoming"]
        self.channel_id = ctx["channel_id"]
        self.decoded = False

    def __str__(self):
        return f'<MSG:{self.op_type} PKT:{self.curr_packet["num"]}/{self.curr_packet["len"]}>'

    def parse(self, stream):
        # print('parse in MsgDecoder')
        # bprint(stream)
        msg = {}
        self.len, stream = split_16le(stream)
        self.op_type, stream = split_16le(stream)
        self.content, stream = split(stream, self.len)

        # print(f'LEN: {msg["len"]} OP: {self.op_type}')
        # stream.print_rest()
        self.try_decode()
        # print(msg)
        self.transport.add_msg(self.ctx, self)
        # print(f'return offset: {stream.bit_offset} / {len(stream.stream)}')
        return stream

    exit = 1

    def init_server(self):
        if not self.ctx["incoming"]:
            return
        curr_map = Map(self)
        GLOBAL["map"] = curr_map

    def decode(self):
        self.data = ByteStream(self.content)
        if self.op_type == SERVER_INIT:
            self.init_server()
        elif self.op_type == PLAYER_SPAWN:
            self.player = Player(self, me=True)
        elif self.op_type == OBSERVER_SPAWN:
            self.player = Player(self)
        elif self.op_type == OBSERVER_UNSPAWN:
            self.pid = self.data.read_u32()
            self.cid = self.data.read_u8()
            print(f"Exit: {PLAYERS[self.cid]}")
            del PLAYERS[self.cid]
            # exit(0)
            # MsgDecoder.exit -= 1
        elif self.op_type == GAME_UPDATE:
            # print(f'READSIZE: {len(self.content)} / {self.content} / {self}')
            # bprint(self.content)
            up_bin = self.read_size_and_bytes()
            up_data = BitStream(up_bin)
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
        if MsgDecoder.exit <= 0:
            print("Exit 20")
            exit(20)

    skip_unk_player = math.inf

    def update_player(self, up_data: BitStream):
        # get by `channel_id` or `channel_id - 1`
        # player = PLAYERS.get(self.channel_id, PLAYERS.get(self.channel_id - 1, None))  # type: Player

        player = PLAYERS.get(self.channel_id, None)  # type: Player
        if not player:
            # print(f'NO PLAYER: {self.channel_id} : {list(PLAYERS.keys())}')
            if MsgDecoder.skip_unk_player > 0:
                MsgDecoder.skip_unk_player -= 1
                return
            print(f"Players: {list(PLAYERS.keys())} CID: {self.channel_id}")
            print(self.transport.curr_packet)
            print("Exit 21")
            exit(21)
        self.log.debug(f"Update player: {player}")
        player.update(self, up_data)

    def update_outbound(self, up_data):
        # if self.curr_packet['num'] == 1433:
        #     self.log.debug(f'{bytes(up_data.rest)}')
        #     exit(112)
        GLOBAL['me'].update_me(self, up_data)

    def update_world(self, up_data):
        pass

    def try_decode(self):
        try:
            self.decode()
            self.decoded = True
        except Exception as e:
            self.log.exception("While decode packet")
