import math
from array import array
import itertools


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
    assert len(bits) == 8
    out = 0
    for i in range(8):
        out += bits[i] << 7 - i
    return out


class Stream:
    def __init__(self, stream):
        self.bit_offset = 0
        bitstring = itertools.chain.from_iterable([to_bits(one_byte) for one_byte in stream])
        self.stream = array('B', bitstring)

    @property
    def rest(self):
        assert len(self.stream[self.bit_offset:]) % 4 == 0
        bytes_list = []
        i = 0
        while i * 8 < len(self.stream):
            idx = i * 8
            bytes_list.append(to_byte(self.stream[idx:idx + 8]))
            i += 1
        return bytes(bytes_list)

    def read_bits(self, bits):
        """
        little endian bits
        """
        out = 0
        for i in range(bits):
            # out += self.stream[self.bit_offset] << i  # reversed order
            out += self.stream[self.bit_offset] << (bits - 1 - i)
            self.bit_offset += 1
        return out

    def read_u8(self):
        return self.read_bits(8)

    def read_u16(self):
        return self.read_bits(16)

    def reset(self):
        self.bit_offset = 0


class MsgDecoder:
    def __init__(self, transport, ctx):
        self.transport = transport
        self.ctx = ctx

    def parse(self, stream):
        print('parse')
        stream = Stream(stream)
        msg = {}
        self.transport.add_msg(self.ctx, msg)
        print('return')
        ret = stream.rest
        print('after ret')
        return ret
