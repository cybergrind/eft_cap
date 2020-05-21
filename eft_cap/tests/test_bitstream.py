from eft_cap.msg_level import Stream


def test_01():
    one_bit = b'\x80\x00\x00'
    s = Stream(one_bit)
    for i in range(1, 10):
        assert s.read_bits(i) == 1 << (i - 1)
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
    assert s.read_u16() == 0b1111_1111_0000_0000
