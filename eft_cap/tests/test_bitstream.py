from eft_cap.bin_helpers import stream_from_le, BitStream


def test_01():
    one_bit = b'\x80\x00\x00'
    s = BitStream(one_bit)
    for i in range(1, 16):
        res = s.read_bits(i)
        exp = 1 << (i - 1)
        exp = min(128, exp)
        assert res == exp, f'I: {i}: Res: {res} Exp: {exp}'
        s.reset()


def test_02():
    two_bits = b'\xc0\x00\x00'
    s = BitStream(two_bits)
    assert s.read_bits(1) == 0b1
    s.reset()
    assert s.read_bits(2) == 0b11
    s.reset()
    assert s.read_bits(3) == 0b110


def test_03():
    all_bits = b'\xff\x00\x00'
    s = BitStream(all_bits)
    assert s.read_bits(1) == 0b1
    s.reset()
    assert s.read_bits(2) == 0b11
    s.reset()
    assert s.read_bits(3) == 0b111
    s.reset()
    assert s.read_bits(4) == 0b1111
    s.reset()
    assert s.read_u16() == 0b0000_0000_1111_1111

def test_04():
    bs = b'\x16\x00'
    s = BitStream(bs)
    assert s.read_bits(16) == 22


def test_05_wordbs():
    bs = b'\x00\x00\x00\x80'
    s = BitStream(bs)
    assert s.read_bits(1) == 1


def test_06_stream_le():
    bs = b'\x00\x00\x00\x80'
    mvd = bytes(stream_from_le(bs))
    assert mvd == b'\x80\x00\x00\x00', f'Converted => {mvd}'

    bs2 = bytes([0x71, 0xc5, 0xdb, 0x19, 0xdd, 0xb4, 0x7c, 0x17])
    target = bytes([0x19, 0xdb, 0xc5, 0x71, 0x17, 0x7c, 0xb4, 0xdd])
    mvd2 = bytes(stream_from_le(bs2))
    assert mvd2 == target, 'Converted => {mvd2} VS {target}'


def test_07_stream_le_3b():
    bs3 = b'\x01\x02\x03'
    mvd3 = bytes(stream_from_le(bs3))
    assert mvd3 == b'\x03\x02\x01'


def test_08_vars():
    # 0x19dbc571177cb4dd
    bs = bytes([0x71, 0xc5, 0xdb, 0x19, 0xdd, 0xb4, 0x7c, 0x17])
    s = BitStream(bs)
    we_want = '0001100111011011110001010111000100010111011111001011010011011101'
    print(s.stream)
    print(we_want)
    # assert bin_str == we_want
    read_11 = s.read_bits(11)
    print(read_11)
    assert read_11 == 0xce
    assert s.read_bits(32) == 0xde2b88bb

    s.reset()
    assert s.read_bits(13) == 0x33b
    assert s.read_bits(32) == 0x78ae22ef
