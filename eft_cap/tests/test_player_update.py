import numpy as np
import pytest
from pathlib import Path
from eft_cap.network_base import NetworkTransport
from eft_cap.bin_helpers import BitStream
from eft_cap.msg_level import GLOBAL, MsgDecoder
from fan_tools.python import rel_path


pytestmark = pytest.mark.asyncio
BitStream.DEBUG = True

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

class FakeMap:
    bound_min = np.array([0.0, 0.0, 0.0], np.float)
    bound_max = np.array([1000.0, 100.0, 1000.0], np.float)

GLOBAL['map'] = FakeMap()

async def test_01(packet_01):
    trans = NetworkTransport(packet_01, FakeArgs())
    trans.trust_session(30849)
    await trans.run(limit=1)
    assert False


def test_02():
    payload = b'\x1c\x00\x87\xce\x98\x80\xc3\xbc\xfbE\x93\x7f\x8a\x88G\x84.\x9c\x33\xc4\xcd\xea\xa1\x90\0x0a\x10\x00\x00\x00\x00'
    trans = NetworkTransport(packet_01, FakeArgs())
    trans.curr_packet = {'data': payload, 'incoming': True, 'num': 0, 'len': len(payload)}
    m = MsgDecoder(trans, {'incoming': True, 'channel_id': 7})
    m.content = payload
    m.op_type = 170
    m.decode()
