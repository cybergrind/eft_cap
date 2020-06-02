import numpy as np
import pytest
from pathlib import Path
from eft_cap.network_base import NetworkTransport
from eft_cap.bin_helpers import BitStream, ByteStream
from eft_cap.msg_level import GLOBAL, MsgDecoder
from fan_tools.python import rel_path


pytestmark = pytest.mark.asyncio
BitStream.DEBUG = True
ByteStream.DEBUG = True

@pytest.fixture
def packet_01():
    async def _inner():
        yield {
            'incoming': True,
            'data': Path(rel_path('packets/01_in_update.bin')).read_bytes(),
        }
    return _inner()


class FakeArgs:
    packets_file = True
    skip = None


async def test_01(packet_01):
    trans = NetworkTransport(packet_01, FakeArgs())
    trans.trust_session(30849)
    await trans.run(limit=1)
    assert False


def test_02_update(shore):
    # shore packet
    payload = (b'\x74\x00\x89\x9c4\x82\xca\x02 -\x1a\xd6 \xf4nMn\x963\x84l\\\x81\x8cx\n\x06\x10\x84'
               b'\x8d\x18)B\x005ed15b72ccf5cb1bf22f522a\x00\x00\x00\x00\x00\x00\xc0\x00\x00'
               b'\x00\x00\x00\x08\x18@\x003:\x00\x06\x185ed15b72ccf5cb1bf22f5223\x00\xc1'
               b'\x00\x00\x00\x00\x00\x18@\x00\x00\x00\x00\x00(')
    trans = NetworkTransport(packet_01, FakeArgs())
    trans.curr_packet = {'data': payload, 'incoming': True, 'num': 0, 'len': len(payload)}
    m = MsgDecoder(trans, {'incoming': True, 'channel_id': 7})
    m.content = payload
    m.op_type = 170
    m.decode()


def test_03_update_string_error(shore):
    payload = (b'\x74\x00\x89<I\x82\xca\x02 8\xb8\xdf\xd4\xa1#\xf6\xb0\x163\x84f\xf4\x8cx\n\x10'
               b'\x10\x84\x8d\x81)B\x00\x06\x185ed13eee06433f6f293b024f\x00\x00\x00\x00'
               b'\x00\xcc\x00\x00\x00\x00\x00\x19@\x00\x00:\x00\x06\x883'
               b'\x185ed13eec8bf8cb2ce5463675\x00\xcd\x00\x00\x00\x00@'
               b'\x00\x00\x00\x00\x00\xa8\x19')
    trans = NetworkTransport(packet_01, FakeArgs())
    trans.curr_packet = {'data': payload, 'incoming': True, 'num': 0, 'len': len(payload)}
    m = MsgDecoder(trans, {'incoming': True, 'channel_id': 7})
    m.content = payload
    m.op_type = 170
    m.decode()
