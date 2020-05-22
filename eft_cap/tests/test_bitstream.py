from eft_cap.msg_level import Stream


def test_01():
    one_bit = b'\x80\x00\x00'
    s = Stream(one_bit)
    for i in range(1, 16):
        res = s.read_bits(i)
        exp = 1 << (i - 1)
        exp = min(128, exp)
        assert res == exp, f'I: {i}: Res: {res} Exp: {exp}'
        s.reset()


def test_02():
    two_bits = b'\xc0\x00\x00'
    s = Stream(two_bits)
    assert s.read_bits(1) == 0b1
    s.reset()
    assert s.read_bits(2) == 0b11
    s.reset()
    assert s.read_bits(3) == 0b110


def test_03():
    all_bits = b'\xff\x00\x00'
    s = Stream(all_bits)
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
    s = Stream(bs)
    assert s.read_bits(16) == 22
