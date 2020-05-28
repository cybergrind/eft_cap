import asyncio
import struct
import scapy
from scapy.layers.l2 import Ether
from scapy.all import load_layer
from multiprocessing import Process, Queue

from eft_cap import bprint


def read_ip(data, offset, hdr_size):
    real_off = offset - hdr_size
    src_bin = data[real_off:real_off+4]
    src = f'{src_bin[0]}.{src_bin[1]}.{src_bin[2]}.{src_bin[3]}'
    return src


def read_port(data, offset, hdr_size):
    port_off = offset - hdr_size
    bport = data[port_off:port_off+2]
    if len(bport) == 0:
        return - 1
    return struct.unpack('>H', bport)[0]


def getTagType(type):
    types = {
        0x00: "TAG_PADDING",
        0x01: "TAG_END",
        0x0A: "TAG_RAW_RSSI",
        0x0B: "TAG_SNR",
        0x0C: "TAG_DATA_RATE",
        0x0D: "TAG_TIMESTAMP",
        0X0F: "TAG_CONTENTION_FREE",
        0X10: "TAG_DECRYPTED",
        0X11: "TAG_FCS_ERROR",
        0X12: "TAG_RX_CHANNEL",
        0X28: "TAG_PACKET_COUNT",
        0X29: "TAG_RX_FRAME_LENGTH",
        0X3C: "TAG_WLAN_RADIO_HDR_SERIAL"
    }
    return types[type]

def processTag(tag,details=False):
    currentTag = None
    i = 0
    while currentTag not in [0x00, 0x01]:
        currentTag = tag[i]
        tagType = getTagType(tag[0])
        tagLength = 0
        if(tagType not in ["TAG_END","TAG_PADDING"]):
            tagLength = ord(tag[1])

        i = i + 1 + tagLength
    return i


class UdpProto(asyncio.Protocol):
    def __init__(self, receiver):
        self.receiver = receiver
        self.fragments = {}
        load_layer('inet')

    # ue.payload.payload.payload.load
    def datagram_received(self, data, addr):
        hdr_size = 0x2a - 1
        tags_len = processTag(data[4:])
        hdr_size += tags_len
        ue = Ether(data[4+tags_len:])
        ip = ue.payload

        if ip.version != 4:
            return

        if ip.proto != 17:
            return


        # if ip.flags == 1:  # multifragment
        # with open('en.packet', 'w') as f:
        #     f.write(str(data))
        udp = ip.payload
        if ip.flags == 1:
            key = f'{ip.src}=>{ip.dst}'
            if key not in self.fragments:
                self.fragments[key] = {'udp': udp, 'packets': {}}
            self.fragments[key]['packets'][ip.frag] = udp.load
            return
        elif ip.frag > 0:
            key = f'{ip.src}=>{ip.dst}'
            if key in self.fragments:
                self.fragments[key]['packets'][ip.frag] = udp.load

                udp = self.fragments[key]['udp']
                ks = sorted(self.fragments[key]['packets'])
                fragments = []
                for k in ks:
                    fragments.append(self.fragments[key]['packets'][k])
                payload = b''.join(fragments)
                import hashlib
                print(f'HASH: {hashlib.md5(payload).hexdigest()}')
                del self.fragments[key]
            else:
                # payload = udp.load
                return
        else:
            if udp.len == 0:
                return
            if not isinstance(udp.payload, scapy.packet.Raw):
                return
            payload = udp.load

        # print(f'FLAGS: {ip.flags} => LEN: {ip.len} => FRAG: {ip.frag} SUM: {ip.chksum} / {udp!r}')
        eft = (16900 <= udp.sport <= 17100) or (16900 <= udp.dport <= 17100)
        if not eft:
            return

        self.receiver({
            'incoming': ip.dst.startswith('192.168.'),
            'data': payload,
            'src_port': udp.sport,
            'dst_port': udp.dport,
        })

        src = read_ip(data, 0x49, hdr_size)
        dst = read_ip(data, 0x4d, hdr_size)
        src_port = read_port(data, 0x51, hdr_size)
        dst_port = read_port(data, 0x53, hdr_size)
        eft = (16900 <= src_port <= 17100) or (16900 <= dst_port <= 17100)

        # if len(data) > 1519:
        #     print(f'Data len: {len(data)}')
        if len(data) > 0x46 - 0x2a and data[0x46-0x2a] == 17:  # UDP
            if len(data) >= 1519:
                print(f'Data: {len(data)}')
                with open('en.packet', 'w') as f:
                    f.write(str(data))
                return

        # print(self.receiver)
        if not eft:
            return

        # print(f'SRC: {src}:{src_port} DST: {dst}:{dst_port} EFT: {eft}')
        data_offset = 0x59 - 0x2a
        # bprint(data)
        # print(f'LEN: {len(data)} DataOFF: {data_offset}')
        # print(f'{src} => {dst}')
        rcvd = data[data_offset:]
        # print(rcvd)
        # bprint(rcvd[:0x64])
        with open('en2.packet', 'w') as f:
            f.write(str(data))

        self.receiver({
            'incoming': dst.startswith('192.168.'),
            'data': rcvd,
            'src_port': src_port,
            'dst_port': dst_port,
        })


async def run(receiver=lambda x: x):
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UdpProto(receiver), local_addr=('0.0.0.0', 37008)
    )
    while True:
        await asyncio.sleep(120)

def main():
    asyncio.run(run())

if __name__ == '__main__':
    main()
