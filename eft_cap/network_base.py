"""

"""
import asyncio
import json
import logging
import struct
from collections import defaultdict
import pathlib
import datetime

from eft_cap.msg_level import MsgDecoder, clear_global
from eft_cap import bprint, split, split_8, split_16, split_16le
import pickle


Z_HEARTBEAT = 0x4
Z_INIT = 0x1
MB_PLAYER_EXIT = 0x3
Z_SKIP = [MB_PLAYER_EXIT]

M_MSG_DELIMITER = 255
M_MSG_COMBINED = 254
CHAN_MAX = 207
FRAGMENTED = [0, 1, 2]


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

    def __init__(self, src, args):
        self.args = args
        self.replay = args.packets_file

        self.session_ok = []
        self.src = src
        self.acks_in = Acks('inbound')
        self.acks_out = Acks('outbound')
        self.fragmented = {True: {0: [], 1: [], 2: []}, False: {0: [], 1: [], 2: []}}
        self.log_path = None
        self.packet_log = None
        self.init_packet_log()

    def init_packet_log(self):
        if self.log_path and self.log_path.stat().st_size == 0:
            if self.packet_log:
                self.packet_log.close()
            self.log_path.unlink()
        self.log_path = pathlib.Path(datetime.datetime.now().strftime('packet_logs/%Y%m%d_%H%M.packet.log'))
        if not self.log_path.parent.exists():
            self.log_path.parent.mkdir(exist_ok=True)
        self.packet_log = self.log_path.open('w')

    async def run(self, limit=None):
        # packet -> {'data', 'incoming'}
        self.packet_num = -1
        skip_num = self.args.skip
        async for packet in self.src:
            self.packet_num += 1
            if skip_num and skip_num > self.packet_num:
                continue

            if self.packet_num % 500 == 0:
                self.log.info(f'Packet: {self.packet_num}')
            if limit and self.packet_num >= limit:
                break
            # noinspection PyBroadException
            try:
                self.process_packet(packet)
                await asyncio.sleep(0)
            except Exception as e:
                self.log.exception(f'When process_packet: Len: {packet["len"]} Num: {packet["num"]}')
                with open('error.packet', 'wb') as f:
                    pickle.dump(packet, f)
                # bprint(packet['data'])
                print('Exit 19')
                if self.replay:
                    exit(19)
        print(f'All packets were read')
        # await asyncio.sleep(300)

    def bin_to_str(self, bytestring):
        out = []
        for b in bytestring:
            s = hex(b)[2:]
            if len(s) == 1:
                s = '0' + s
            out.append(s)
        return ':'.join(out)

    def save_packet(self, packet):
        if self.args.packets_file:
            return
        self.packet_log.write(
            json.dumps({'incoming': packet['incoming'],
            'data': self.bin_to_str( packet['data'])})
        )
        self.packet_log.write('\n')

    def process_packet(self, packet):
        self.save_packet(packet)
        packet['len'] = len(packet['data'])
        packet['num'] = self.packet_num
        self.curr_packet = packet

        # if self.curr_packet['len'] >= 900:
        #     print(f'===============> MSG: {self.curr_packet["num"]}/{self.curr_packet["len"]}')

        stream = packet['data']
        if len(stream) < 3:
            self.log.warning(f'Skip packet. Length < 3')
            return
        (conn, ) = struct.unpack('>H', stream[:2])
        if conn == 0:
            op = stream[2]
            if op in Z_SKIP:
                self.log.info(f'SKIP Packet: {self.curr_packet["len"]}')
                return
            elif op == Z_HEARTBEAT:
                assert len(stream) == 27
                if len(stream) == 27:
                    sess_id, = struct.unpack('<H', stream[25:])
                    self.trust_session(sess_id)
                return
            elif op == Z_INIT:
                sess_id, = struct.unpack(('<H', stream[5:7]))
                self.trust_session(sess_id)
                self.new_session()
                return
        else:
            ctx = {'pck_len': len(packet['data']), 'incoming': packet['incoming']}

            b_cps, stream = split(stream, 6)
            # print(f'Parse: {b_cps}')
            (connection_id, packet_id, session_id) = struct.unpack('>HHH', b_cps)
            if session_id not in self.session_ok:
                self.log.info(f'Skip packet, no session: {session_id} vs {self.session_ok}')
                self.log.info(self.curr_packet)
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
            # bprint(stream)
            self.log.warning(f'Cannot process packet: {self.packet_num} => {packet}')
            # exit(16)

    def trust_session(self, sess_id):
        if sess_id not in self.session_ok:
            self.session_ok.append(sess_id)

    def add_msg(self, ctx, msg=None):
        ctx.setdefault('message', []).append({
            'channel_id': ctx['channel_id'],
            'msg_len': ctx['msg_len'],
            # 'msg_id': ctx['msg_id'],
            'msg': msg,
        })

    def without_fragment(self, _id, fragments):
        for fragment in fragments:
            if fragment['frag_id'] == _id:
                continue
            yield fragment

    def get_next_message(self, stream, ctx):
        # https://forum.unity.com/threads/binary-protocol-specification.417831/#post-3495130
        if len(stream) == 0:
            yield False, stream
        channel_id = stream[0]
        assert channel_id not in FRAGMENTED
        # print(f'CHID: {channel_id}')
        if channel_id == M_MSG_DELIMITER:
            stream = self.extractMessageHeader(stream, ctx)
            # channel_id + msg_len
            channel_id = ctx['channel_id']
            msg_len = ctx['msg_len']
            self.log.debug(f'CTX: {ctx}')
            assert msg_len <= len(stream), f'{msg_len} vs {len(stream)}'
            # print(f'FF message: len={msg_len} stream len={len(stream)}')
            stream, after = split(stream, msg_len)
            order_id, stream = split_16(stream)
            # 78084
            # oid, stream = split_8(stream)

            while True:
                if len(stream) == 0:
                    if after:
                        yield from self.get_next_message(after, ctx)
                        return
                    else:
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

                    fragment = self.get_fragment(ctx, frag_id, inner_channel_id)
                    chunks = fragment['chunks']

                    self.log.debug(f'FID: {frag_id} FIDX: {frag_idx} TOTAL: {frag_amnt}')
                    # _, stream = split(stream, 4)

                    if frag_idx in chunks:
                        if chunks[frag_idx] != fragm_stream:
                            self.log.warning(f'I: {chunks.keys()}')
                            self.log.warning(f'FID: {frag_id} FIDX: {frag_idx} TOTAL: {frag_amnt}')
                            self.log.warning(chunks[frag_idx])
                            self.log.warning(fragm_stream)
                            if self.replay:
                                print('Exit 199')
                                exit(199)

                    chunks[frag_idx] = fragm_stream

                    self.log.debug(f'{frag_idx}: ID: {frag_id} LEN: {len(fragment)} VS {frag_amnt}/')
                    if len(self.fragmented) > 0:
                        self.log.debug(f'FRAGMENTED: {list(self.fragmented)}')

                    if len(chunks) == frag_amnt: # or frag_idx == frag_amnt - 1:
                        fragments = []
                        for i in range(frag_amnt):
                            fragments.append(chunks[i])

                        bin_msg = b''.join(fragments)
                        self.log.debug(f'Assemble {frag_id} LEN: {len(bin_msg)}')
                        # print(bin_msg)
                        # bprint(bin_msg)
                        while len(bin_msg) > 2:
                            msg = MsgDecoder(self, ctx)
                            bin_msg = msg.parse(bin_msg)
                            self.log.debug(f'Processed message in fragmented. Remains: {len(bin_msg)}')
                            yield True, msg
                        # print(f'After parse: {bin_msg}')
                        if bin_msg != b'' and len(bin_msg) > 3:
                            print(f'BinRest: {bin_msg}')
                            # print(self.curr_packet)
                            print('Exit 15')
                            if self.replay:
                                exit(15)
                        # assert bin_msg == b''
                        # print(f'Msg: {msg.op_type}')
                        yield True, msg
                        chan_fragments = self.fragmented[ctx['incoming']][inner_channel_id]
                        chan_fragments[:] = self.without_fragment(frag_id, chan_fragments)
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
                    if self.replay:
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
            if self.replay:
                exit(14)

        elif channel_id == M_MSG_COMBINED:
            print(self.curr_packet)
            print('Exit 4')
            if self.replay:
                exit(4)
            return False, stream

        # 487 -> 256 : 231
        if len(stream) > 2:
            stream = self.extractMessageHeader(stream, ctx)
            msg_len = ctx['msg_len']
            if ctx['channel_id'] in FRAGMENTED:
                if self.replay:
                    print('FRAGMENTED')
                    exit(111)
            msg_stream, stream = split(stream, msg_len)
            # print(f'Split msg stream: {len(msg_stream)} Rest: {len(stream)}')
            if len(msg_stream) >= msg_len:
                msg_id, msg_stream = split_16(msg_stream)
                ordered_id, msg_stream = split_8(msg_stream)
                ctx['msg_id'] = msg_id
            while len(msg_stream) > 3:
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

    def get_fragment(self, ctx, frag_id, inner_channel_id):
        key = f'{ctx["incoming"]}_{inner_channel_id}_{frag_id}'
        fragmented = self.fragmented[ctx['incoming']][inner_channel_id]
        if len(fragmented) == 0:
            fragment = {'frag_id': frag_id, 'chunks': {}}
            fragmented.append(fragment)

        elif len(fragmented) == 1:
            fragment = fragmented[0]
            if fragment['frag_id'] != frag_id:
                fragment = {'frag_id': frag_id, 'chunks': {}}
                fragmented.append(fragment)
        else:
            fragment = fragmented[-1]
            if fragment['frag_id'] != frag_id:
                fragment = {'frag_id': frag_id, 'chunks': {}}
                fragmented.append(fragment)

            for maybe_stale in list(fragmented[:-1]):
                stale_id = fragment['frag_id']
                if abs(stale_id - frag_id) > 4:
                    self.log.debug(f'Drop stale fragment: {key}')
                    fragmented[:] = self.without_fragment(stale_id, fragmented)
        return fragment

    def extractMessageHeader(self, stream, ctx):
        channel_id, stream = split_8(stream)
        ctx['channel_id'] = channel_id
        # if channel_id in FRAGMENTED:
        #     print(f'Channel id: {channel_id}')
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

    def new_session(self):
        """Called when new game has started"""
        self.log.warning('New session')
        self.fragmented = {True: {0: [], 1: [], 2: []}, False: {0: [], 1: [], 2: []}}
        clear_global()
        self.session_ok = []
        self.init_packet_log()

