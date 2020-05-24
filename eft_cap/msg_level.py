import math
from array import array
import itertools
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

    def read_bytes(self, num_bytes):
        required = num_bytes * 8
        remains = len(self.stream) - self.bit_offset
        if required > remains:
            self.print_rest()
            print(f'Read: {num_bytes}')
            print('Exit 17')
            exit(17)
            raise ParsingError(f'Need: {required} Remains: {remains} Offset: {self.bit_offset}')
        assert self.bit_offset % 8 == 0
        boff = int(self.bit_offset / 8)
        print(f'Get bytes: {num_bytes} BOFF: {boff} OFF: {boff + num_bytes}')
        resp = self.orig_stream[boff:(boff + num_bytes)]
        self.bit_offset += num_bytes * 8
        return resp

    def read_u8(self):
        return self.read_bits(8)

    def read_u16(self):
        b1 = self.read_bits(8)
        b2 = self.read_bits(8) << 8
        print(f'B1: {b1} B2: {b2}')
        return b1 + b2

    def reset(self):
        self.bit_offset = 0


class MsgDecoder:
    def __init__(self, transport, ctx):
        self.transport = transport
        self.ctx = ctx

    def parse(self, stream):
        print('parse in MsgDecoder')
        # bprint(stream)
        stream = Stream(stream)
        msg = {}
        self.len = msg['len'] = stream.read_u16()
        self.op_type = msg['op_type'] = stream.read_u16()
        print(f'LEN: {msg["len"]} OP: {self.op_type}')
        # stream.print_rest()
        self.content = msg['content'] = stream.read_bytes(msg['len'])
        # print(msg)
        self.transport.add_msg(self.ctx, self)
        print(f'return offset: {stream.bit_offset} / {len(stream.stream)}')
        ret = stream.rest
        if len(ret) > 60:
            print(f'after ret: {ret[:60]} ....')
        else:
            print(f'After ret: {ret}')
        return ret
