import itertools
import logging
import math
import struct
from array import array
from functools import wraps, lru_cache
from pathlib import Path
from bitarray import bitarray

import numpy as np

from eft_cap import bprint, ParsingError



def packed(fmt, single=True):
    def _wrapped(func):
        @wraps(func)
        def _inner(*args, **kwargs):
            bin_resp = func(*args, **kwargs)
            unpacked = struct.unpack(fmt, bin_resp)
            return unpacked[0] if single else unpacked
        return _inner
    return _wrapped


class ByteStream:
    log = logging.getLogger("ByteStream")
    DEBUG = False

    def __init__(self, stream):
        self.byte_offset = 0
        self.orig_stream = stream
        self.named_positions = {}
        self.named_set = set()
        self.positions = []
        self.next_bytes = []
        self.auto = 0

    def read_bytes(self, num):
        out = self.orig_stream[self.byte_offset : self.byte_offset + num]

        if len(out) != num:
            # self.log.error(
            #     f"OS: {self.orig_stream[:10]} OFST: {self.byte_offset} NUM: {num} L: {len(self.orig_stream)}"
            # )
            raise ParsingError(f'OS: {out[:20]} OFST: {self.byte_offset} NUM: {num} L: {len(self.orig_stream)}')
        self.byte_offset += num
        if self.DEBUG:
            self.next_bytes = self.orig_stream[self.byte_offset:]
        assert len(out) == num
        return out

    def debug_rest(self, num, back=0):
        out = []
        old_bo = self.byte_offset
        self.byte_offset -= back
        for i in range(num):
            s = hex(self.read_u8())[2:]
            if len(s) == 1:
                s = '0' + s
            out.append(s)
        self.byte_offset = old_bo
        return ' '.join(out)

    def dump_to(self, fname: str, position=None, size=None):
        write_func = Path(fname).write_bytes
        if position is None:
            write_func(self.orig_stream[self.byte_offset:])
        elif isinstance(position, int):
            if size is None:
                write_func(self.orig_stream[self.bytes_offset:])
            else:
                write_func(self.orig_stream[self.bytes_offset:self.byte_offset + size])
        elif isinstance(position, str):
            write_func(self.orig_stream[self.named_positions[position]:])
        else:
            raise NotImplementedError

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

    @packed('<d')
    def read_double(self):
        return self.read_bytes(8)

    def read_bool(self):
        return self.read_u8() > 0

    def read_vector(self):
        return np.array([
            self.read_f32(),
            self.read_f32(),
            self.read_f32(),
        ], np.float)

    def read_string(self):
        size = self.read_7bit_int()
        out = []
        for i in range(size):
            out.append(chr(self.read_u8()))
        return ''.join(out)

    def read_7bit_int(self):
        num = 0
        num2 = 0
        while num2 != 35:
            b = self.read_u8()
            num |= (b & 127) << num2
            num2 += 7
            if (b & 128) == 0:
                return num
        return 0

    def store_pos(self, name=None, auto=False):
        if auto:
            assert name is not None
            self.auto += 1
            name = f'{name}_{self.auto}'
        self.positions.append(self.byte_offset)
        if name:
            self.named_set.add(self.byte_offset)
            self.named_positions[name] = self.byte_offset

    def pos_to_name(self, pos):
        for name, named_pos in self.named_positions.items():
            if named_pos == pos:
                return name

    def store_name(self, name, back=-1):
        pos = self.positions[back]
        assert pos not in self.named_set, f'POS is already saved as: {self.pos_to_name(pos)}'
        self.named_set.add(pos)
        self.named_positions[name] = pos


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
        out.append(to_byte(bits[i * 8: i * 8 + 8]))
    return bytes(out)


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


class BitStream:
    log = logging.getLogger("BitStream")
    DEBUG = False

    def __init__(self, stream, reverse=True):
        self.bit_offset = 0
        self.orig_stream = stream
        be_stream = stream_from_le(stream)
        if reverse:
            self.stream_be = itertools.chain.from_iterable([to_bits(one_byte) for one_byte in be_stream])
        else:
            self.stream_be = [to_bits(one_byte) for one_byte in stream]
        # self.stream = array("B", bitstring)
        self.length_limit = len(stream) * 8
        self.stream = bitarray(self.stream_be, endian='big')
        self.next_bytes = None
        # print(f'Stream: {stream}')
        # b = bitarray(endian='little')
        # self.stream = b.frombytes(bytes(stream))

    @property
    def rest(self):
        # assert len(self.stream[self.bit_offset:]) % 8 == 0, f'Off: {self.bit_offset}'
        while self.bit_offset <= len(self.stream) - 8:
            yield self.read_bits(8)

    def print_rest(self):
        bit = self.bit_offset
        bprint(self.rest)
        self.bit_offset = bit
        if self.DEBUG:
            self.next_bytes = self.stream[self.bit_offset:]

    def align(self):
        off = self.bit_offset % 8
        # print(f'Align: -> {off} vs {self.bit_offset}')
        if off:
            self.read_bits(8 - off)
        assert self.bit_offset % 8 == 0

    DECODE = {
        1: '>B',
        2: '>H',
        4: '>I',
        8: '>Q',
    }

    @lru_cache(maxsize=None)
    def calc_shift(self, bits):
        shift = 0
        if bits % 8:
            shift = 8 - bits % 8
        return shift

    def read_bits(self, bits=1):
        if self.bit_offset + bits > self.length_limit:

            raise ParsingError(f'Overflow: need {bits} have: {self.length_limit - self.bit_offset} L: {self.length_limit}')
        if bits == 1:
            bit = self.stream[self.bit_offset]
            self.bit_offset += bits
            if self.DEBUG:
                self.next_bytes = self.stream[self.bit_offset:]
            return bit
        bs = self.stream[self.bit_offset : self.bit_offset + bits]
        # bs = "".join([str(i) for i in bs])
        if not bs:
            return 0
        self.bit_offset += bits
        if self.DEBUG:
            self.next_bytes = self.stream[self.bit_offset:]

        out = 0
        bs = bs.tobytes()

        while True:
            len_bs = len(bs)
            # print(f'OUT: {out} => {len_bs} / {bs}')
            if len_bs == 0:
                break
            elif len_bs >= 8:
                out += struct.unpack('>Q', bs[:8])[0] << (8 * (len_bs - 8))
                bs = bs[8:]
            elif len_bs >= 4:
                out += struct.unpack('>I', bs[:4])[0] << (8 * (len_bs - 4))
                bs = bs[4:]
            elif len_bs >= 2:
                out += struct.unpack('>H', bs[:2])[0] << (8 * (len_bs - 2))
                bs = bs[2:]
            elif len_bs == 1:
                out += struct.unpack('>B', bs[:2])[0]
                break
            else:
                raise NotImplementedError
        shift = self.calc_shift(bits)
        if bits % 8:
            shift = 8 - bits % 8
        # print(f'SHIFT: {shift}')
        return out >> shift

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

    def read_bytes_aligned(self, num_bytes):
        self.align()
        out = []
        c = 0
        # when not aligned to word - read as LE
        # after it's aligned - just read rest of the stream
        while True:
            curr_byte = int(self.bit_offset / 8)
            if curr_byte % 4 != 0:
                c += 1
                out.append(self.read_bits(8))
            else:
                break
        num_bytes -= c
        assert num_bytes >= 0

        self.bit_offset += num_bytes * 8
        if self.DEBUG:
            self.next_bytes = self.stream[self.bit_offset:]

        return bytes(out) + self.orig_stream[curr_byte:curr_byte + num_bytes]

    def read_bytes(self, num_bytes):
        self.align()
        return bytes([self.read_bits(8) for i in range(num_bytes)])

    def read_u8(self):
        return self.read_bits(8)

    # @packed(">H")
    def read_u16(self):
        return self.read_bits(16)

    # @packed(">I")
    def read_u32(self):
        return self.read_bits(32)

    # @packed(">Q")
    def read_u64(self):
        return self.read_bits(32) << 32 + self.read_bits(32)

    @property
    def aligned(self):
        return self.bit_offset % 8 == 0

    # @packed(">f")
    def read_f32(self):
        return struct.unpack('>f', struct.pack('>I', self.read_bits(32)))

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

    def read_limited_string(self, char_min, char_max):
        if self.read_bits():
            return
        self.align()
        num = self.read_u32()
        assert num < 8096, f'Want: {num} chars'
        char_bits = bits_required(ord(char_min), ord(char_max))
        out = []
        for i in range(num):
            char = self.read_bits(char_bits) + ord(char_min)
            out.append(char)
        return out

    def reset(self):
        self.bit_offset = 0

    def read_check(self, what=0):
        self.align()
        return what == self.read_u32()


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
