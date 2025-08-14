import numpy as np
from Viewport import Viewport

from simulator.SensorTwin.sensor_twin_utilities import Coordinate

tc = Coordinate(0, 0, 0)


def init_test1():
    try:
        vp = Viewport()
        return False
    except Exception as e:
        if type(e) is TypeError:
            return True
        else:
            print(f"Init_test1: Wrong exception thrown. Received {type(e)}")
            return False


def init_test2():
    try:
        vp = Viewport(Coordinate(0, 0, 0), 360, 95)
        loc = vp.position == Coordinate(0, 0, 0)
        if not loc:
            print(
                f"init_test2: Failed to initialize viewport location. "
                f"Received {vp.location}, expected {Coordinate(0, 0, 0)}"
            )
        ort = vp.orientation == 0
        if not ort:
            print(
                f"init_test2: Failed to initialize viewport orientation. "
                f"Received {vp.orientation}, expected {0}"
            )
        cant = vp.vertical_rotation == 90
        if not cant:
            print(
                f"init_test2: Failed to initialize viewport vertical cant. "
                f"Received {vp.vertical_rotation}, expected {90}"
            )
        return loc and ort and cant
    except Exception as e:
        print(f"init_test2: Exception {e} thrown")
        return False


def set_vertical_cant_test():
    try:
        tc = Coordinate(0, 0, 0)
        vp1 = Viewport(tc, 0, 0)
        vp1.set_vertical_cant(-50)
        t1 = vp1.get_vertical_cant() == 0
        if not t1:
            print(
                f"get_vertical_cant_test: Failed to bound floor of vertical cant. "
                f"Expected 0 degrees, set to {vp1.get_vertical_cant()}"
            )

        vp1.set_vertical_cant(45)
        t2 = vp1.get_vertical_cant() == 45
        if not t2:
            print(
                f"get_vertical_cant_test: Failed to set vertical cant. "
                f"Expected 45 degrees, set to {vp1.get_vertical_cant()}"
            )

        vp1.set_vertical_cant(180)
        t3 = vp1.get_vertical_cant() == 90
        if not t3:
            print(
                f"get_vertical_cant_test: Failed to bound ceiling of vertical cant. "
                f"Expected 90 degrees, set to {vp1.get_vertical_cant()}"
            )

        return t1 and t2 and t3
    except Exception as e:
        print(f"get_vertical_cant_test: Exception {e} thrown")
        return False


def adjust_vertical_cant_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.adjust_vertical_cant(-45)
        t1 = vp1.get_vertical_cant() == 0
        if not t1:
            print(
                f"adjust_vertical_cant_test: Failed to bound floor of vertical cant. "
                f"Expected 0 degrees, set to {vp1.get_vertical_cant()}"
            )

        vp1.adjust_vertical_cant(45)
        t2 = vp1.get_vertical_cant() == 45
        if not t2:
            print(
                f"adjust_vertical_cant_test: Failed to adjust vertical cant positively. "
                f"Expected 45 degrees, set to {vp1.get_vertical_cant()}"
            )

        vp1.adjust_vertical_cant(180)
        t3 = vp1.get_vertical_cant() == 90
        if not t3:
            print(
                f"adjust_vertical_cant_test: Failed to bound ceiling of vertical cant. "
                f"Expected 90 degrees, set to {vp1.get_vertical_cant()}"
            )

        vp1.adjust_vertical_cant(-10)
        t4 = vp1.get_vertical_cant() == 80
        if not t4:
            print(
                f"adjust_vertical_cant_test: Failed to adjust vertical cant negatively. "
                f"Expected 90 degrees, set to {vp1.get_vertical_cant()}"
            )
        return t1 and t2 and t3 and t4
    except Exception as e:
        print(f"set_vertical_cant_test: Exception {e} thrown")
        return False


def set_view_orientation_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.set_view_orientation(-90)
        t1 = vp1.get_view_orientation() == 270
        if not t1:
            print(
                f"set_view_orientation_test: Failed to properly set orientation when given negative value. "
                f"Expected 270 degrees, set to {vp1.get_view_orientation()}"
            )
        vp1.set_view_orientation(180)
        t2 = vp1.get_view_orientation() == 180
        if not t2:
            print(
                f"set_view_orientation_test: Failed to properly set orientation given standard value. "
                f"Expected 180 degrees, set to {vp1.get_view_orientation()}"
            )
        vp1.set_view_orientation(500)
        t3 = vp1.get_view_orientation() == 140
        if not t3:
            print(
                f"set_view_orientation_test: Failed to properly set orientation given overflowed value. "
                f"Expected 140 degrees, set to {vp1.get_view_orientation()}"
            )
        return t1 and t2 and t3
    except Exception as e:
        print(f"set_view_orientation_test: Exception {e} thrown")
        return False


def adjust_view_orientation_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.adjust_view_orientation(-45)
        t1 = vp1.get_view_orientation() == 315
        if not t1:
            print(
                f"adjust_view_orientation_test: Failed to properly adjust set orientation given negative value. "
                f"Expected 315 degrees, set to {vp1.get_view_orientation()}"
            )
        vp1.set_view_orientation(315)
        vp1.adjust_view_orientation(90)
        t2 = vp1.get_view_orientation() == 45
        if not t2:
            print(
                f"adjust_view_orientation_test: Failed to properly adjust set orientation given positive value. "
                f"Expected 45 degrees, set to {vp1.get_view_orientation()}"
            )
        vp1.set_view_orientation(0)
        vp1.adjust_view_orientation(450)
        t3 = vp1.get_view_orientation() == 90
        if not t3:
            print(
                f"adjust_view_orientation_test: Failed to properly adjust set orientation given overflowed value. "
                f"Expected 90 degrees, set to {vp1.get_view_orientation()}"
            )
        return t1 and t2 and t3
    except Exception as e:
        print(f"adjust_view_orientation_test: Exception {e} thrown")
        return False


def set_global_position_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        c1 = Coordinate(1.0, 2.5, 4.0)
        vp1.set_global_position(c1)
        t1 = vp1.get_global_position() == c1
        t2 = vp1.get_absolute_altitude() == 4.0
        if not t1:
            print(
                f"set_global_position_test: Failed to set global position of viewport given standard coordinate. "
                f"Expected {c1}, received {vp1.get_global_position()}"
            )
        if not t2:
            print(
                f"set_global_position_test: Failed to set altitude while setting global position of viewport. "
                f"Expected {c1.alt}, received {vp1.get_absolute_altitude()}"
            )
        return t1 and t2
    except Exception as e:
        print(f"set_global_position_test: Exception {e} thrown")
        return False


def adjust_global_position_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        c1 = Coordinate(1.0, 2.0, 3.0)
        vp1.adjust_global_position(c1, 1)
        t1 = vp1.get_global_position() == c1
        if not t1:
            print(
                f"adjust_global_position_test: Failed to adjust global position along coordinate vector with timestep 1. "
                f"Expected {c1}, resulted in {vp1.get_global_position()}"
            )
        vp1.set_global_position(tc)
        vp1.adjust_global_position(c1, 0.1)
        t2 = vp1.get_global_position() == Coordinate(0.1, 0.2, 0.3)
        if not t2:
            print(
                f"adjust_global_position_test: Failed to adjust global position along coordinate vector with fractional timestep. "
                f"Expected {Coordinate(0.1, 0.2, 0.3)}, resulted in {vp1.get_global_position()}"
            )
        return t1 and t2
    except Exception as e:
        print(f"adjust_global_position_test: Exception {e} thrown")
        return False


def derive_hfov_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.set_vfov(40)
        vp1.set_dfov(80)
        vp1.derive_hfov()
        t1 = vp1.horizontal_fov == 69.28203
        if not t1:
            print(
                f"derive_hfov_test: Failed to calculate horizontal FOV from vertical and diagonal. "
                f"Expected 69.282, resulted in {vp1.horizontal_fov}"
            )
        return t1
    except Exception as e:
        print(f"derive_hfov_test: Exception {e} thrown")
        return False


def derive_vfov_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.set_hfov(40)
        vp1.set_dfov(80)
        vp1.derive_vfov()
        t1 = vp1.vertical_fov == 69.28203
        if not t1:
            print(
                f"derive_vfov_test: Failed to calculate vertical FOV from horizontal and diagonal. "
                f"Expected 69.282, resulted in {vp1.vertical_fov}"
            )
        return t1
    except Exception as e:
        print(f"derive_vfov_test: Exception {e} thrown")
        return False


def derive_dfov_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.set_hfov(60)
        vp1.set_vfov(40)
        vp1.derive_dfov()
        t1 = vp1.diagonal_fov == 72.11103
        if not t1:
            print(
                f"derive_dfov_test: Failed to calculate diagonal FOV from horizontal and vertical. "
                f"Expected 72.111, resulted in {vp1.diagonal_fov}"
            )
        return t1
    except Exception as e:
        print(f"derive_dfov_test: Exception {e} thrown")
        return False


def derive_ar_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.set_hfov(60)
        vp1.set_vfov(60)
        vp1.derive_aspect_ratio()
        t1 = vp1.aspect_ratio == 1
        if not t1:
            print(
                f"derive_ar_test: Failed to calculate aspect ratio from HFOV and VFOV. Expected"
                f"1.0, resulted in {vp1.aspect_ratio}"
            )
        vp1.set_vfov(30)
        vp1.derive_aspect_ratio()
        t2 = round(vp1.aspect_ratio, 5) == 2.15470
        if not t2:
            print(
                f"derive_ar_test: Failed to calculate aspect ratio from HFOV and VFOV. Expected"
                f"2.0, resulted in {vp1.aspect_ratio}"
            )
        return t1 and t2
    except Exception as e:
        print(f"derive_ar_test: Exception {e} thrown")
        return False


def mag_to_ground_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.translate(2, 2, 5)
        vp1.set_vertical_cant(45)
        mag = vp1.magnitude_to_ground(vp1.get_vertical_cant())
        t1 = round(mag, 5) == 7.07107
        if not t1:
            print(
                f"mag_to_ground_test: Failed to calculate magnitude to ground on 45 degree angle. "
                f"Expected 7.071, resulted in {mag}"
            )
        vp1.set_vertical_cant(30)
        mag = vp1.magnitude_to_ground(vp1.get_vertical_cant())
        t2 = round(mag, 5) == 10
        if not t2:
            print(
                f"mag_to_ground_test: Failed to calculate magnitude to ground on 30 degree angle. "
                f"Expected 10, resulted in {mag}"
            )
        vp1.set_vertical_cant(0.1)
        mag = vp1.magnitude_to_ground(vp1.get_vertical_cant())
        t3 = round(mag, 5) == 2864.79043
        if not t3:
            print(
                f"mag_to_ground_test: Failed to calculate magnitude to ground on .1 degree angle. "
                f"Expected 2864.79043, resulted in {mag}"
            )
        tc.set_global_pos(0, 0, 0)
        return t1 and t2 and t3
    except Exception as e:
        print(f"mag_to_ground_test: Exception {e} thrown")
        tc.set_global_pos(0, 0, 0)
        return False


def centerpoint_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.translate(2, 2, 5)
        vp1.set_vertical_cant(45)
        cp = vp1.get_center_point()
        res1 = Coordinate(2, 7, 0)
        t1 = cp == res1
        if not t1:
            print(
                f"centerpoint_test: Failed to calculate centerpoint at {vp1.get_vertical_cant()} cant and "
                f"{vp1.get_view_orientation()}. Expected {res1}, resulted in {cp}"
            )
        vp1.set_view_orientation(45)
        cp = vp1.get_center_point()
        res2 = Coordinate(
            2 + round((5 * np.sqrt(2) / 2), 5), 2 + round((5 * np.sqrt(2) / 2), 5), 0
        )
        t2 = cp == res2
        if not t2:
            print(
                f"centerpoint_test: Failed to calculate centerpoint at {vp1.get_vertical_cant()} cant and "
                f"{vp1.get_view_orientation()}. Expected {res2}, resulted in {cp}"
            )
        tc.set_global_pos(0, 0, 0)
        return t1 and t2
    except Exception as e:
        print(f"centerpoint_test: Exception {e} thrown")
        tc.set_global_pos(0, 0, 0)
        return False


def top_values_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.translate(2, 2, 5)
        vp1.set_vertical_cant(45)
        vp1.set_vfov(40)
        tp, tlen = vp1.get_top_values()
        rlen1 = 10.72253
        res1 = Coordinate(2, 2 + rlen1, 0)
        t1 = tp == res1 and round(tlen, 5) == rlen1
        if not t1:
            print(
                f"top_values_test: Failed to calculate top intercept and ground length. Expected "
                f"{res1} given mag {rlen1}, resulted in {tp} given mag {tlen}"
            )
        vp1.set_view_orientation(45)
        tp, tlen = vp1.get_top_values()
        rlen2 = rlen1
        res2 = Coordinate(
            round(np.cos(np.deg2rad(45)) * rlen2 + 2, 3),
            round(np.sin(np.deg2rad(45)) * rlen2 + 2, 3),
            0,
        )
        tp.lat = round(tp.lat, 3)
        tp.long = round(tp.long, 3)
        t2 = tp == res2 and round(tlen, 5) == rlen2
        if not t2:
            print(
                f"top_values_test: Failed to calculate top intercept and ground length. Expected "
                f"{res2} given mag {rlen2}, resulted in {tp} given mag {tlen}"
            )
        vp1.set_view_orientation(0)
        vp1.set_vertical_cant(10)
        vp1.set_vfov(60)
        tp, tlen = vp1.get_top_values()
        rlen3 = 2864.8
        tp.lat = round(tp.lat, 1)
        res3 = Coordinate(2, 2 + rlen3, 0)
        t3 = tp == res3 and round(tlen, 1) == rlen3
        if not t3:
            print(
                f"top_values_test: Failed to calculate top intercept and ground length. Expected "
                f"{res3} given mag {rlen3}, resulted in {tp} given mag {tlen}"
            )
        tc.set_global_pos(0, 0, 0)
        return t1 and t2 and t3
    except Exception as e:
        print(f"top_values_test: Exception {e} thrown")
        tc.set_global_pos(0, 0, 0)
        return False


def bottom_values_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.translate(2, 2, 5)
        vp1.set_vertical_cant(45)
        vp1.set_vfov(40)
        bp, blen = vp1.get_bottom_values()
        rlen1 = 2.33154
        res1 = Coordinate(2, 2 + rlen1, 0)
        t1 = res1 == bp and round(blen, 5) == rlen1
        if not t1:
            print(
                f"bottom_values_test: Failed to calculate bottom intercept and ground length. Expected "
                f"{res1} given mag {rlen1}, resulted in {bp} given mag {blen}"
            )
        vp1.set_view_orientation(45)
        bp, blen = vp1.get_bottom_values()
        rlen2 = rlen1
        res2 = Coordinate(
            round(np.cos(np.deg2rad(45)) * rlen2 + 2, 3),
            round(np.sin(np.deg2rad(45)) * rlen2 + 2, 3),
            0,
        )
        bp.lat = round(bp.lat, 3)
        bp.long = round(bp.long, 3)
        t2 = bp == res2 and round(blen, 5) == rlen2
        if not t2:
            print(
                f"bottom_values_test: Failed to calculate top intercept and ground length. Expected "
                f"{res2} given mag {rlen2}, resulted in {bp} given mag {blen}"
            )
        vp1.set_view_orientation(0)
        vp1.set_vertical_cant(80)
        vp1.set_vfov(60)
        bp, blen = vp1.get_bottom_values()
        rlen3 = -1.81985
        res3 = Coordinate(2, round(2 + rlen3, 5), 0)
        bp.lat = round(bp.lat, 5)
        t3 = res3 == bp and round(blen, 5) == round(rlen3, 5)
        if not t3:
            print(
                f"bottom_values_test: Failed to calculate bottom intercept and ground length. Expected "
                f"{res3} given mag {rlen3}, resulted in {bp} given mag {blen}"
            )
        tc.set_global_pos(0, 0, 0)
        return t1 and t2 and t3
    except Exception as e:
        print(f"bottom_values_test: Exception {e} thrown")
        tc.set_global_pos(0, 0, 0)
        return False


def lateral_point_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.translate(2, 2, 5)
        vp1.set_vertical_cant(45)
        vp1.set_vfov(40)
        vp1.set_hfov(60)
        tv = vp1.get_top_values()
        bv = vp1.get_bottom_values()
        top_corners = vp1.get_lateral_points(tv[0], tv[1])
        bottom_corners = vp1.get_lateral_points(bv[0], bv[1])
        t1 = top_corners[0] == Coordinate(-4.19066, 12.72253, 0) and top_corners[
            1
        ] == Coordinate(8.19066, 12.72253, 0)
        t2 = bottom_corners[0] == Coordinate(0.65389, 4.33154, 0) and bottom_corners[
            1
        ] == Coordinate(3.34611, 4.33154, 0)
        if not t1:
            print(
                f"lateral_point_test: Failed to derive lateral bounding box top corners. Expected "
                f"{Coordinate(-4.191, 12.72253, 0)} and {Coordinate(8.191, 12.72253, 0)}, resulted in "
                f"{top_corners[0]} and {top_corners[1]}"
            )
        if not t2:
            print(
                f"lateral_point_test: Failed to derive lateral bounding box bottom corners. Expected "
                f"{Coordinate(0.654, 4.33154, 0)} and {Coordinate(3.346, 4.33154, 0)}, resulted in "
                f"{bottom_corners[0]} and {bottom_corners[1]}"
            )
        vp1.set_view_orientation(45)
        tv = vp1.get_top_values()
        bv = vp1.get_bottom_values()
        top_corners = vp1.get_lateral_points(tv[0], tv[1])
        bottom_corners = vp1.get_lateral_points(bv[0], bv[1])
        t3 = top_corners[0] == Coordinate(7.55040, 11.61356, 0) and top_corners[
            1
        ] == Coordinate(11.61356, 7.55040, 0)
        t4 = bottom_corners[0] == Coordinate(3.20690, 4.09040, 0) and bottom_corners[
            1
        ] == Coordinate(4.09040, 3.20690, 0)
        if not t3:
            print(
                f"lateral_point_test: Failed to derive lateral bounding box top corners. Expected "
                f"{Coordinate(7.55040, 11.61356, 0)} and {Coordinate(11.61356, 7.55040, 0)}, resulted in "
                f"{top_corners[0]} and {top_corners[1]}"
            )
        if not t4:
            print(
                f"lateral_point_test: Failed to derive lateral bounding box bottom corners. Expected "
                f"{Coordinate(3.20690, 4.09040, 0)} and {Coordinate(4.09040, 3.20690, 0)}, resulted in "
                f"{bottom_corners[0]} and {bottom_corners[1]}"
            )
        tc.set_global_pos(0, 0, 0)
        return t1 and t2 and t3 and t4
    except Exception as e:
        print(f"lateral_point_test: Exception {e} thrown")
        tc.set_global_pos(0, 0, 0)
        return False


def find_corners_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.translate(2, 2, 5)
        vp1.set_vertical_cant(45)
        vp1.set_hfov(60)
        vp1.set_vfov(40)
        corners = vp1.find_corners()
        rc = [
            Coordinate(-4.19066, 12.72253, 0),
            Coordinate(0.65389, 4.33154, 0),
            Coordinate(3.34611, 4.33154, 0),
            Coordinate(8.19066, 12.72253, 0),
        ]
        t1 = True
        for i in range(4):
            if corners[i] != rc[i]:
                t1 = False
        if not t1:
            print(
                f"find_corners_test: Failed to derive bounding box corners. Expected {rc}, resulted "
                f"in {corners}"
            )
        tc.set_global_pos(0, 0, 0)
        return t1
    except Exception as e:
        print(f"find_corners_test: Exception {e} thrown")
        tc.set_global_pos(0, 0, 0)
        return False


def update_bounding_box_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.translate(2, 2, 5)
        vp1.set_vertical_cant(45)
        vp1.set_hfov(60)
        vp1.set_vfov(40)
        t1 = vp1.bounding_box.corners is None and vp1.bounding_box.orientation == 0
        if not t1:
            print(
                "update_bounding_box_test: Failed to properly initialize bounding box"
            )
        vp1.update_bounding_box()
        rc = [
            Coordinate(-4.19066, 12.72253, 0),
            Coordinate(0.65389, 4.33154, 0),
            Coordinate(3.34611, 4.33154, 0),
            Coordinate(8.19066, 12.72253, 0),
        ]
        t2 = vp1.bounding_box.corners == rc and vp1.bounding_box.orientation == 0
        if not t2:
            print(
                f"update_bounding_box_test: Failed to update viewport bounding box. Expected {rc}, "
                f"resulted in {vp1.bounding_box.corners} with orientation {vp1.bounding_box.orientation}"
            )
        tc.set_global_pos(0, 0, 0)
        return t1 and t2
    except Exception as e:
        print(f"update_bounding_box_test: Exception {e} thrown")
        tc.set_global_pos(0, 0, 0)
        return False


def harness_init():
    func_list = []
    func_list.append(init_test1)
    func_list.append(init_test2)
    func_list.append(set_vertical_cant_test)
    func_list.append(adjust_vertical_cant_test)
    func_list.append(set_view_orientation_test)
    func_list.append(adjust_view_orientation_test)
    func_list.append(set_global_position_test)
    func_list.append(adjust_global_position_test)
    func_list.append(derive_hfov_test)
    func_list.append(derive_vfov_test)
    func_list.append(derive_dfov_test)
    func_list.append(derive_ar_test)
    func_list.append(mag_to_ground_test)
    func_list.append(centerpoint_test)
    func_list.append(top_values_test)
    func_list.append(bottom_values_test)
    func_list.append(lateral_point_test)
    func_list.append(find_corners_test)
    func_list.append(update_bounding_box_test)

    return func_list


def main():
    test_ctr = 0
    successes = 0
    failure_list = []
    test_list = harness_init()

    print("===========Starting Viewport testing===========\n")
    # Tests here
    for func in test_list:
        test_ctr += 1
        if func():
            successes += 1
        else:
            failure_list.append((test_ctr, func.__name__))

    print("===========Completed Viewport testing===========")
    print(f"Test Results: {successes} / {test_ctr} cases passed.")
    if len(failure_list) != 0:
        print("Failed test cases:")
        for entries in failure_list:
            print(f"    Test ID: {entries[0]} - Test Name: {entries[1]}")
    print()


if __name__ == "__main__":
    main()
