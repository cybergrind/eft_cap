"""

"""
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
            except Exception as e:
                self.log.exception(f'When process_packet: {packet}')

    def process_packet(self, packet):
        b_channel, stream = split(packet['data'], 2)
        (channel, ) = struct.unpack('>H', b_channel)
        if channel == 0:
            op = stream[0]
            if op in Z_SKIP:
                return
        self.log.warning(f'Cannot process packet: {self.packet_num} => {packet}')
