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


def test_04_update_throw(shore):
    payload = (b'\x44\x00\x8a\xa6\x10\x84\xc8\x9a\x81\x15\x90ZH\xba#\xde"\xb93\x04\xedb'
               b'\x02\xa1X\n\x00\x0e\x80\x013\x185ecefd59478cc53d1d7341ee\xab\x00\x00'
               b'\x00\x00\x00\x15@\x00\x00\x00\x00\x00h')
    trans = NetworkTransport(packet_01, FakeArgs())
    trans.curr_packet = {'data': payload, 'incoming': True, 'num': 0, 'len': len(payload)}
    m = MsgDecoder(trans, {'incoming': True, 'channel_id': 7})
    m.content = payload
    m.op_type = 170
    m.decode()


def test_05_read_transfer(shore):
    payload = (b'\x64\x00\x89:\xca\x82\xcb\xbe\xeb|\xc0\xc7,\x89c\x1d\xe3'
               b'\x15SDh\xdb\x8cx\n\xd0\x08\x84\x8d\x811v\x00\x06'
               b'\x185ed070f1bb713341547e77de\x1a5e4e9770e3174373744f251a64'
               b'\x01\x00\x00\x00\x00\x00\x01\t\x00\x00\x00\x00\x00(!@')
    trans = NetworkTransport(packet_01, FakeArgs())
    trans.curr_packet = {'data': payload, 'incoming': True, 'num': 0, 'len': len(payload)}
    m = MsgDecoder(trans, {'incoming': True, 'channel_id': 7})
    m.content = payload
    m.op_type = 170
    m.decode()


def test_06_read_split(shore):
    payload = (b'\x98\x00\x89\xa8\xc9\x82\xcb\xe0\x9d|\xc0\xc7,\x89c\x1d\xe3'
               b'\x15SDh\xdb\x8cx\n\xd0\x08\x84\x8d\x81/\xdc\x00\x06'
               b'\x185ed070f1bb713341547e77de#\x00\x00\x00\x00\x00\x00'
               b'\x00\x00\x00\x00\x00\x00\x01'
               b'\x185ed00a2497355152f1702b50\x017!'
               b'\x185ed12968491bdb6a68425cc7\ncartridges'
               b'\x01\x00\x00\x00\x08\x00\x00\x00\x01@\x00\x00\x00\x00\x00\x08!')
    trans = NetworkTransport(packet_01, FakeArgs())
    trans.curr_packet = {'data': payload, 'incoming': True, 'num': 0, 'len': len(payload)}
    m = MsgDecoder(trans, {'incoming': True, 'channel_id': 7})
    m.content = payload
    m.op_type = 170
    m.decode()
