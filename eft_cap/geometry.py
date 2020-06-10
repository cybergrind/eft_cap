import numpy as np

"""
maps
shoreline:
{'x': 458.6, 'y': -54.6, 'z': 135.3} -- corner fence near car, exit to tunnels => 2187, 744 
{'x': -158.0, 'y': -13.0, 'z': -352.2} - river left side top, near fence => 1380, 1381
{'x': -1014.4, 'y': -65.1, 'z': 298.9} -- rw, barrel cache near river => 252, 524
 
{'x': -148.9, 'y': -9.4, 'z': -332.4} - top river, electro nearest to top-river, inside

lng/lat => z/x
135.3, 458.6 => 1124, 387.1   / village
-352.2, -158 => 709.5, 61.1   / fence
298.9, -1014.4 => 130.1, 499.9  / barrel

woods:

"""


def calc_transform_matrix(source_points, target_points):
    """
    points = [[px1, py1, pz1], [px2, py2, pz2]]
    """
    inv = np.linalg.pinv(source_points)
    return np.dot(inv, target_points)



def shore():
    pic = np.array([[755.1, 2187.75, 1], [117.06, 1381.09, 1], [973.56, 254.625, 1]], np.float)
    coord = np.array([[135.3, 458.6, 1], [-352.2, -158, 1], [298.9, -1014.4, 1]], np.float)
    trans = calc_transform_matrix(pic, coord)
    pic_corners = np.array([[0.0, 0.0, 1], [1500., 2415., 1]], np.float)
    print(np.dot(pic_corners, trans))


def main():
    a = np.array([[458.6, 135.3, 1], [-1014.4, 298.9, 1], [-158.0, -352.2, 1]], np.float)
    b = np.array([[2187, 744, 1], [252, 524, 1], [1380, 1381, 1]], np.float)
    print(a)
    i = np.linalg.pinv(a)
    trans = np.dot(i, b)
    print(trans)
    c = np.array([[-148.9, -332.4, 1]], np.float)
    print(np.dot(c, trans))
    shore()


if __name__ == '__main__':
    main()
