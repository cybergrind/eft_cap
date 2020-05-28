from eft_cap.msg_level import angle, norm_angle
from pytest import approx


def test_01():
    a = angle([45, 45], [90, 0])
    assert a == approx(-45.0)
    a = angle([45, -45], [90, 0])
    assert norm_angle(a) == approx(45.0)
