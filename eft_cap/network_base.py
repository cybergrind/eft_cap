"""

"""
import asyncio
import logging
import struct


Z_HEARTBEAT = 0x4
Z_INIT = 0x1
Z_SKIP = [Z_HEARTBEAT]

M_MSG_DELIMITER = 255
M_MSG_COMBINED = 254


def split(data, num_bytes):
    return data[:num_bytes], data[num_bytes:]

def split_byte(data):
    byte, ret = split(data, 1)
    return byte[0], ret


class NetworkTransport:
    packet_num: int
    log = logging.getLogger('NetworkTransport')

    def __init__(self, src):
        self.src = src

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
            ctx = {}
            if self.decode_data_packet(stream, ctx):
                return
        self.log.warning(f'Cannot process packet: {self.packet_num} => {packet}')

    def decode_data_packet(self, stream, ctx):
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
        channel_id = stream[0]
        if channel_id == M_MSG_DELIMITER:
            stream = self.extractMessageHeader(stream, ctx)
            b_header, stream = split(stream, 2)
            (msg_id,) = struct.unpack('>H', b_header)
            ctx['msg_id'] = msg_id
            print(ctx)
            print(f'Len: {len(stream)} / {stream}')
            exit(1)
        if channel_id in (M_MSG_COMBINED, M_MSG_DELIMITER):
            return False
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
        # extractMessageHeader
        stream = self.extractMessageHeader(stream, ctx)
        msg_len = ctx['msg_len']
        if msg_len > len(stream):
            print(ctx)
            print(stream)
            print(self.curr_packet)
            print(f'Pckt: {self.packet_num} Len: {len(self.curr_packet["data"])}')
        print(f'exit: {self.packet_num} / len: {len(self.curr_packet["data"])} / {self.curr_packet["data"]}')
        exit(1)
        # checkLengthIsValid


    def new_session(self):
        """Called when new game has started"""
        pass
