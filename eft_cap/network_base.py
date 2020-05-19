"""

"""
import asyncio
import logging
import struct


Z_HEARTBEAT = 0x4
Z_INIT = 0x1
Z_SKIP = [Z_HEARTBEAT]


def split(data, num_bytes):
    return data[:num_bytes], data[num_bytes:]


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
        b_channel, stream = split(packet['data'], 2)
        (channel, ) = struct.unpack('>H', b_channel)
        if channel == 0:
            op = stream[0]
            if op in Z_SKIP:
                return
            elif op == Z_INIT:
                self.new_session()
                return
        else:
            ctx = {'channel': channel}
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

        print(f'CTX: {ctx} / {stream}')
        return False

    def new_session(self):
        """Called when new game has started"""
        pass
