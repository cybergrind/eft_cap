import math

import numpy as np
import vg
import scipy.spatial

def norm_angle(angl):
    if angl > 180:
        angl -= 360
    if angl < -180:
        angl += 360
    return angl


def _angle(pos1, pos2, rot):
    vectors = np.array([pos1, pos2])
    dist = scipy.spatial.distance.pdist(vectors, 'cosine')
    angl = np.rad2deg(np.arccos(1 - dist))
    sign = np.array(np.sign(np.cross(pos1, pos2).dot(np.array([0., -1., 0.], np.float))))

    # 0 means collinear: 0 or 180. Let's call that clockwise.
    sign[sign == 0] = 1

    angl = sign * angl

    angl += rot[0]

    if angl == np.NaN:
        return 0
    return -int(norm_angle(angl))


def angle(pos1, pos2, rot):
    v1 = np.array([0, 0, -1], np.float)
    v2 = pos1 - pos2
    angl = vg.signed_angle(v2, v1, look=vg.basis.y) + rot[0]

    if np.isnan(angl):
        return 0.0
    return -int(norm_angle(angl))


def fwd_vector(pitch, yaw, pos):
    elevation = math.radians(-pitch)
    heading = math.radians(yaw)
    return {
        'x': math.cos(elevation) * math.sin(heading),
        'y': math.sin(elevation),
        'z': math.cos(elevation) * math.cos(heading),
    }


def dist(a, b):
    return np.linalg.norm(a - b)


def euler_to_quaternion(roll, pitch, yaw):
    qx = math.sin(roll / 2) * math.cos(pitch / 2) * math.cos(yaw / 2) - math.cos(
        roll / 2
    ) * math.sin(pitch / 2) * math.sin(yaw / 2)
    qy = math.cos(roll / 2) * math.sin(pitch / 2) * math.cos(yaw / 2) + math.sin(
        roll / 2
    ) * math.cos(pitch / 2) * math.sin(yaw / 2)
    qz = math.cos(roll / 2) * math.cos(pitch / 2) * math.sin(yaw / 2) - math.sin(
        roll / 2
    ) * math.sin(pitch / 2) * math.cos(yaw / 2)
    qw = math.cos(roll / 2) * math.cos(pitch / 2) * math.cos(yaw / 2) + math.sin(
        roll / 2
    ) * math.sin(pitch / 2) * math.sin(yaw / 2)

    return [qx, qy, qz, qw]


def quaternion_to_euler(x, y, z, w):
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll = math.degrees(math.atan2(t0, t1))
    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    pitch = math.degrees(math.asin(t2))
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw = math.degrees(math.atan2(t3, t4))
    return np.array([yaw, pitch, roll])
