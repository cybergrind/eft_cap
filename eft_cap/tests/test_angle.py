import numpy as np

from eft_cap.trig_helpers import norm_angle, angle
from pytest import approx


def test_01():
    a = angle(np.array([45, 0, 45]), np.array([90, 0, 0]), [0, 0, 0])
    assert a == approx(135.0)
    a = angle(np.array([45, 0, -45]), np.array([90, 0, 0]), [0, 0, 0])
    assert norm_angle(a) == approx(45.0)
    a = angle(np.array([90, 0, 0]), np.array([45, 0, -45]), [0, 0, 0])
    assert norm_angle(a) == approx(-135.0)
