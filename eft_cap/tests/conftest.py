import numpy as np
import pytest

from eft_cap.msg_level import GLOBAL


class FakeShoreMap:
    bound_min = np.array([-1041., -105., -447.89001465], np.float)
    bound_max = np.array([519, 45, 589.89], np.float)


class FakeWoodsMap:
    bound_min = np.array([-628., -78., -247], np.float)
    bound_max = np.array([572, 71.2, 452.7], np.float)


class FakeFactoryMap:
    bound_min = np.array([-68.8, -10.3, -86], np.float)
    bound_max = np.array([89.19, 29.7, 94], np.float)


@pytest.fixture
def shore():
    GLOBAL['map'] = FakeShoreMap()


@pytest.fixture
def woods():
    GLOBAL['map'] = FakeWoodsMap()


@pytest.fixture
def factory():
    GLOBAL['map'] = FakeFactoryMap()
