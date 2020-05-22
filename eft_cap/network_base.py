"""

"""
import asyncio
import logging
import struct
from eft_cap.msg_level import MsgDecoder
from eft_cap import bprint
import pickle


Z_HEARTBEAT = 0x4
Z_INIT = 0x1
Z_SKIP = [Z_HEARTBEAT]

M_MSG_DELIMITER = 255
M_MSG_COMBINED = 254
CHAN_MAX = 207


def split(data, num_bytes):
    return data[:num_bytes], data[num_bytes:]


def split_byte(data):
    byte, ret = split(data, 1)
    return byte[0], ret


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
        self.src = src
        self.acks_in = Acks('inbound')
        self.acks_out = Acks('outbound')

    async def run(self, limit=None):
        # packet -> {'data', 'incoming'}
        self.packet_num = -1
        for packet in self.src:
            self.packet_num += 1
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

    def process_packet(self, packet):
        self.curr_packet = packet
        stream = packet['data']
        (conn, ) = struct.unpack('>H', stream[:2])
        if conn == 0:
            op = stream[2]
            if op in Z_SKIP:
                return
            elif op == Z_INIT:
                self.new_session()
                return
        else:
            ctx = {'pck_len': len(packet['data'])}

            b_cps, stream = split(stream, 6)
            # print(f'Parse: {b_cps}')
            (connection_id, packet_id, session_id) = struct.unpack('>HHH', b_cps)
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

            while True:
                has_packet, stream = self.get_next_message(stream, ctx)
                print(f'HAS_PACKET: {has_packet}')
                if has_packet:
                    stream = MsgDecoder(self, ctx).parse(stream)
                else:
                    if len(stream) > 0:
                        self.log.warning(f'Cannot parse rest: {ctx}')
                        bprint(stream)
                    break
        if len(stream) > 0:
            self.log.warning(f'Cannot process packet: {self.packet_num} => {packet}')

    def add_msg(self, ctx, msg=None):
        ctx.setdefault('message', []).append({
            'channel_id': ctx['channel_id'],
            'msg_len': ctx['msg_len'],
            'msg_id': ctx['msg_id'],
            'msg': msg,
        })

    def get_next_message(self, stream, ctx):
        channel_id = stream[0]
        print(f'CHID: {channel_id}')
        if channel_id == M_MSG_DELIMITER:
            stream = self.extractMessageHeader(stream, ctx)
            (msg_id,) = struct.unpack('>H', stream[:2])
            acks = self.acks_in if self.curr_packet['incoming'] else self.acks_out
            ctx['msg_id'] = msg_id
            if not acks.read_message(msg_id):
                print('Recur 1')
                exit(5)
                return self.get_next_message(stream, ctx)
            b_header, stream = split(stream, 2)
            print('Recur 2')
            self.add_msg(ctx)
            return self.get_next_message(stream, ctx)
        if channel_id in (M_MSG_COMBINED, M_MSG_DELIMITER):
            exit(4)
            return False, stream
        return self.extractMessage(stream, ctx)

    def extractMessageHeader(self, stream, ctx):
        channel_id, stream = split_byte(stream)
        ctx['channel_id'] = channel_id
        b_len = stream[0]
        if b_len & 0x80:
            b_len, stream = split(stream, 2)
            (msg_len,) = struct.unpack('>H', b_len)
            msg_len &= 0x7fff  # reset high bit
        else:
            msg_len, stream = split_byte(stream)
        ctx['msg_len'] = msg_len
        return stream

    def extractMessage(self, stream, ctx):
        stream = self.extractMessageHeader(stream, ctx)
        print(ctx)
        bprint(stream)
        msg_len = ctx['msg_len']
        if msg_len > len(stream):
            print(f'Pckt: {self.packet_num} Len: {len(self.curr_packet["data"])}')
            return False, stream
        print(f'exit: {self.packet_num} / len: {len(self.curr_packet["data"])} / {self.curr_packet["data"]}')
        return True, stream
        exit(1)
        # checkLengthIsValid

    def new_session(self):
        """Called when new game has started"""
        pass
