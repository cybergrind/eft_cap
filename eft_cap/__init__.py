import struct


def bprint(stream):
    bstring = []
    for i in stream:
        bstring.append(hex(i)[2:])
    print(' '.join(bstring))


class ParsingError(Exception):
    pass


def split(data, num_bytes):
    return data[:num_bytes], data[num_bytes:]


def split_8(data):
    byte, ret = split(data, 1)
    return byte[0], ret


def split_16(data):
    two_bytes, ret = split(data, 2)
    return struct.unpack('>H', two_bytes)[0], ret


def split_16le(data):
    two_bytes, ret = split(data, 2)
    return struct.unpack('<H', two_bytes)[0], ret
