"""

"""
import asyncio
import logging
import struct
from collections import defaultdict

from eft_cap.msg_level import MsgDecoder
from eft_cap import bprint
import pickle


Z_HEARTBEAT = 0x4
Z_INIT = 0x1
Z_SKIP = []

M_MSG_DELIMITER = 255
M_MSG_COMBINED = 254
CHAN_MAX = 207
FRAGMENTED = [0, 1, 2]


def split(data, num_bytes):
    return data[:num_bytes], data[num_bytes:]


def split_8(data):
    byte, ret = split(data, 1)
    return byte[0], ret


def split_16(data):
    two_bytes, ret = split(data, 2)
    return struct.unpack('>H', two_bytes)[0], ret


class Acks:
    def __init__(self, name):
        self.name = name
        self.window_size = 0xffff / 2 - 1
        self.head = self.window_size - 1
        self.tail = 1
        self.acks = [False for x in range(0xffff)]

    def read_message(self, msg_id):
        max_d = 0xffff
        raw_d = abs(msg_id - self.head)
        dist = raw_d if raw_d < (max_d / 2) else max_d - raw_d
        if (dist > self.window_size):
            return False
        if msg_id < self.tail or msg_id > self.head:
            for i in range(dist):
                self.acks[i] = False
                self.tail = (self.tail + 1) % len(self.acks)
                self.head = (self.head + 1) % len(self.acks)

        acked = self.acks[msg_id]
        if not acked:
            self.acks[msg_id] = True
        print(f'Ret acked: {not acked}')
        return not acked


class NetworkTransport:
    packet_num: int
    log = logging.getLogger('NetworkTransport')

    def __init__(self, src):
        self.session_ok = []
        self.src = src
        self.acks_in = Acks('inbound')
        self.acks_out = Acks('outbound')
        self.fragmented = defaultdict(dict)

    async def run(self, limit=None):
        # packet -> {'data', 'incoming'}
        self.packet_num = -1
        for packet in self.src:
            self.packet_num += 1
            if self.packet_num % 500 == 0:
                print(f'Packet: {self.packet_num}')
            if limit and self.packet_num >= limit:
                break
            # noinspection PyBroadException
            try:
                self.process_packet(packet)
                await asyncio.sleep(0)
            except Exception as e:
                self.log.exception(f'When process_packet: {packet}')
                with open('error.packet', 'wb') as f:
                    pickle.dump(packet, f)
                bprint(packet['data'])
                print('Exit 19')
                exit(19)


    def process_packet(self, packet):
        packet['len'] = len(packet['data'])
        packet['num'] = self.packet_num
        self.curr_packet = packet
        stream = packet['data']
        if len(stream) < 3:
            print(f'Skip packet. Length < 3')
            return
        (conn, ) = struct.unpack('>H', stream[:2])
        if conn == 0:
            op = stream[2]
            if op in Z_SKIP:
                return
            elif op == Z_HEARTBEAT:
                assert len(stream) == 27
                if len(stream) == 27:
                    sess_id, = struct.unpack('<H', stream[25:])
                    if sess_id not in self.session_ok:
                        self.session_ok.append(sess_id)
                return
            elif op == Z_INIT:
                self.new_session()
                return
        else:
            ctx = {'pck_len': len(packet['data'])}

            b_cps, stream = split(stream, 6)
            # print(f'Parse: {b_cps}')
            (connection_id, packet_id, session_id) = struct.unpack('>HHH', b_cps)
            if session_id not in self.session_ok:
                print(f'Skip packet, no session: {session_id} vs {self.session_ok}')
                print(self.curr_packet)
                return
            ctx.update({
                'connection_id': connection_id,
                'packet_id': packet_id,
                'session_id': session_id,
            })
            b_acks, stream = split(stream, 2 + 4 * 4)
            if len(stream) == 0:
                return True
            elif len(stream) < 2:
                self.log.warning(f'Error message: {stream}')
                return True

            for (msg_ok, msg) in self.get_next_message(stream, ctx):
                if not msg_ok:
                    stream = msg
                elif msg.op_type == 147:  # ServerInit
                    # self.new_session()
                    pass
        if len(stream) > 0:
            bprint(stream)
            self.log.warning(f'Cannot process packet: {self.packet_num} => {packet}')
            exit(16)

    def add_msg(self, ctx, msg=None):
        ctx.setdefault('message', []).append({
            'channel_id': ctx['channel_id'],
            'msg_len': ctx['msg_len'],
            # 'msg_id': ctx['msg_id'],
            'msg': msg,
        })

    def get_next_message(self, stream, ctx):
        # https://forum.unity.com/threads/binary-protocol-specification.417831/#post-3495130
        if len(stream) == 0:
            yield False, stream
        channel_id = stream[0]
        # print(f'CHID: {channel_id}')
        if channel_id == M_MSG_DELIMITER:
            stream = self.extractMessageHeader(stream, ctx)
            # channel_id + msg_len
            channel_id = ctx['channel_id']
            msg_len = ctx['msg_len']
            assert msg_len == len(stream), f'{msg_len} vs {len(stream)}'
            # print(f'FF message: len={msg_len} stream len={len(stream)}')
            order_id, stream = split_16(stream)
            # 78084
            # oid, stream = split_8(stream)

            while True:
                if len(stream) == 0:
                    yield False, stream
                    return
                inner_channel_id = stream[0]
                if inner_channel_id in FRAGMENTED:
                    # bprint(stream)
                    stream = self.extractMessageHeader(stream, ctx)
                    inner_msg_len = ctx['msg_len']
                    fragm_stream, stream = split(stream, inner_msg_len)
                    # print(f'IMSGLEN: {inner_msg_len} vs {len(stream)}')
                    assert inner_msg_len <= len(fragm_stream)
                    bfrag, fragm_stream = split(fragm_stream, 3)
                    frag_id, frag_idx, frag_amnt = struct.unpack('>BBB', bfrag)
                    # print(f'FID: {frag_id} FIDX: {frag_idx} TOTAL: {frag_amnt}')
                    # _, stream = split(stream, 4)
                    self.fragmented[frag_id][frag_idx] = fragm_stream
                    if frag_idx == frag_amnt - 1:
                        fragments = []
                        for i in range(frag_amnt):
                            fragments.append(self.fragmented[frag_id][i])
                        bin_msg = b''.join(fragments)
                        # print('Assemble ')
                        # bprint(bin_msg)
                        while len(bin_msg) > 2:
                            msg = MsgDecoder(self, ctx)
                            bin_msg = msg.parse(bin_msg)
                            # print(f'Processed message in fragmented. Remains: {len(bin_msg)}')
                            yield True, msg
                        # print(f'After parse: {bin_msg}')
                        if bin_msg != b'':
                            # print(self.curr_packet)
                            print('Exit 15')
                            exit(15)
                        assert bin_msg == b''
                        # print(f'Msg: {msg.op_type}')
                        yield True, msg
                    else:
                        yield False, stream
                elif inner_channel_id == M_MSG_COMBINED:
                    _, stream = split_8(stream)
                else:
                    print(self.curr_packet)
                    print(f'Inner channel id: {inner_channel_id}')
                    msg = MsgDecoder(self, ctx)
                    stream = msg.parse(stream)
                    yield True, msg
                    # print('Rest is: ')
                    # bprint(stream)
                    print('Exit 18')
                    exit(18)

                    inner_msg_len = ctx['msg_len']
                    # print(f'Inner channel id: {inner_channel_id} / Rest len: {len(stream)}')
                    if len(stream) == 0:
                        yield False, stream
                        return
                    (msg_stream, stream) = split(stream, inner_msg_len)
                    try:
                        msg = MsgDecoder(self, ctx).parse(stream)
                    except Exception as e:
                        self.log.exception('MSG DECODER')
                        print('Exit 13')
                        exit(13)
                    yield True, msg
            print('Exit 14')
            exit(14)
        elif channel_id == M_MSG_COMBINED:
            print(self.curr_packet)
            print('Exit 4')
            exit(4)
            return False, stream

        # 487 -> 256 : 231
        if len(stream) > 2:
            stream = self.extractMessageHeader(stream, ctx)
            msg_len = ctx['msg_len']

            msg_stream, stream = split(stream, msg_len)
            # print(f'Split msg stream: {len(msg_stream)} Rest: {len(stream)}')
            msg_id, msg_stream = split_16(msg_stream)
            ordered_id, msg_stream = split_8(msg_stream)
            ctx['msg_id'] = msg_id
            while len(msg_stream) > 0:
                msg = MsgDecoder(self, ctx)
                # bprint(stream)
                msg_stream = msg.parse(msg_stream)
                # print(f'Decoded simple message [{self.packet_num}]: {msg.content}')
                yield True, msg
            # print('After all')
            # bprint(msg_stream)
            if len(stream) > 2:
                # print(f'Recur into {stream}')
                # bprint(stream)
                yield from self.get_next_message(stream, ctx)
            else:
                yield False, stream

    def extractMessageHeader(self, stream, ctx):
        channel_id, stream = split_8(stream)
        ctx['channel_id'] = channel_id
        b_len = stream[0]
        if b_len & 0x80:
            b_len, stream = split(stream, 2)
            (msg_len,) = struct.unpack('>H', b_len)
            msg_len &= 0x7fff  # reset high bit
            # print(f'Good msg len: {msg_len}')
        else:
            msg_len, stream = split_8(stream)
            # print(f'One bit msg len: {msg_len}')
        ctx['msg_len'] = msg_len
        return stream

    def extractMessage(self, stream, ctx):
        print('Exit 19')
        exit(19)
        stream = self.extractMessageHeader(stream, ctx)
        return MsgDecoder(self, ctx).parse(stream)

    def new_session(self):
        """Called when new game has started"""
        print('New session')
        self.fragmented = defaultdict(dict)
