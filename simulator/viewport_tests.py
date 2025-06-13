from Viewport import Viewport
from utilities import Coordinate

tc = Coordinate(0, 0, 0)

def init_test1():
    try:
        vp = Viewport()
        return False
    except Exception as e:
        if type(e) == TypeError:
            return True
        else:
            print(f"Init_test1: Wrong exception thrown. Received {type(e)}")
            return False

def init_test2():
    try:
        vp = Viewport(Coordinate(0, 0, 0), 360, 95)
        loc = (vp.position == Coordinate(0, 0, 0))
        if not loc:
            print(f"init_test2: Failed to initialize viewport location. "
                  f"Received {vp.location}, expected {Coordinate(0, 0, 0)}")
        ort = (vp.orientation == 0)
        if not ort:
            print(f"init_test2: Failed to initialize viewport orientation. "
                  f"Received {vp.orientation}, expected {0}")
        cant = (vp.vertical_rotation == 90)
        if not cant:
            print(f"init_test2: Failed to initialize viewport vertical cant. "
                  f"Received {vp.vertical_rotation}, expected {90}")
        return loc and ort and cant
    except Exception as e:
        print(f"init_test2: Exception {e} thrown")
        return False
    
def set_vertical_cant_test():
    try:
        tc = Coordinate(0, 0, 0)
        vp1 = Viewport(tc, 0, 0)
        vp1.set_vertical_cant(-50)
        t1 = (vp1.get_vertical_cant() == 0)
        if not t1:
            print(f"get_vertical_cant_test: Failed to bound floor of vertical cant. "
                  f"Expected 0 degrees, set to {vp1.get_vertical_cant()}")

        vp1.set_vertical_cant(45)
        t2 = (vp1.get_vertical_cant() == 45)
        if not t2:
            print(f"get_vertical_cant_test: Failed to set vertical cant. "
                  f"Expected 45 degrees, set to {vp1.get_vertical_cant()}")

        vp1.set_vertical_cant(180)
        t3 = (vp1.get_vertical_cant() == 90)
        if not t3:
            print(f"get_vertical_cant_test: Failed to bound ceiling of vertical cant. "
                  f"Expected 90 degrees, set to {vp1.get_vertical_cant()}")
        
        return t1 and t2 and t3
    except Exception as e:
        print(f"get_vertical_cant_test: Exception {e} thrown")
        return False

def adjust_vertical_cant_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.adjust_vertical_cant(-45)
        t1 = (vp1.get_vertical_cant() == 0)
        if not t1:
            print(f"adjust_vertical_cant_test: Failed to bound floor of vertical cant. "
                  f"Expected 0 degrees, set to {vp1.get_vertical_cant()}")

        vp1.adjust_vertical_cant(45)
        t2 = (vp1.get_vertical_cant() == 45)
        if not t2:
            print(f"adjust_vertical_cant_test: Failed to adjust vertical cant positively. "
                  f"Expected 45 degrees, set to {vp1.get_vertical_cant()}")

        vp1.adjust_vertical_cant(180)
        t3 = (vp1.get_vertical_cant() == 90)
        if not t3:
            print(f"adjust_vertical_cant_test: Failed to bound ceiling of vertical cant. "
                  f"Expected 90 degrees, set to {vp1.get_vertical_cant()}")
        
        vp1.adjust_vertical_cant(-10)
        t4 = (vp1.get_vertical_cant() == 80)
        if not t4:
            print(f"adjust_vertical_cant_test: Failed to adjust vertical cant negatively. "
                  f"Expected 90 degrees, set to {vp1.get_vertical_cant()}")
        return t1 and t2 and t3 and t4
    except Exception as e:
        print(f"set_vertical_cant_test: Exception {e} thrown")
        return False
    
def set_view_orientation_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.set_view_orientation(-90)
        t1 = (vp1.get_view_orientation() == 270)
        if not t1:
            print(f"set_view_orientation_test: Failed to properly set orientation when given negative value. "
                  f"Expected 270 degrees, set to {vp1.get_view_orientation()}")
        vp1.set_view_orientation(180)
        t2 = (vp1.get_view_orientation() == 180)
        if not t2:
            print(f"set_view_orientation_test: Failed to properly set orientation given standard value. "
                  f"Expected 180 degrees, set to {vp1.get_view_orientation()}")
        vp1.set_view_orientation(500)
        t3 = (vp1.get_view_orientation() == 140)
        if not t3:
            print(f"set_view_orientation_test: Failed to properly set orientation given overflowed value. "
                  f"Expected 140 degrees, set to {vp1.get_view_orientation()}")
        return t1 and t2 and t3
    except Exception as e:
        print(f"set_view_orientation_test: Exception {e} thrown")
        return False
    
def adjust_view_orientation_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        vp1.adjust_view_orientation(-45)
        t1 = (vp1.get_view_orientation() == 315)
        if not t1:
            print(f"adjust_view_orientation_test: Failed to properly adjust set orientation given negative value. "
                  f"Expected 315 degrees, set to {vp1.get_view_orientation()}")
        vp1.set_view_orientation(315)
        vp1.adjust_view_orientation(90)
        t2 = (vp1.get_view_orientation() == 45)
        if not t2:
            print(f"adjust_view_orientation_test: Failed to properly adjust set orientation given positive value. "
                  f"Expected 45 degrees, set to {vp1.get_view_orientation()}")
        vp1.set_view_orientation(0)
        vp1.adjust_view_orientation(450)
        t3 = (vp1.get_view_orientation() == 90)
        if not t3:
            print(f"adjust_view_orientation_test: Failed to properly adjust set orientation given overflowed value. "
                  f"Expected 90 degrees, set to {vp1.get_view_orientation()}")
        return t1 and t2 and t3
    except Exception as e:
        print(f"adjust_view_orientation_test: Exception {e} thrown")
        return False

def set_global_position_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        c1 = Coordinate(1.0, 2.5, 4.0)
        vp1.set_global_position(c1)
        t1 = (vp1.get_global_position() == c1)
        t2 = (vp1.get_absolute_altitude() == 4.0)
        if not t1:
            print(f"set_global_position_test: Failed to set global position of viewport given standard coordinate. "
                  f"Expected {c1}, received {vp1.get_global_position()}")
        if not t2:
            print(f"set_global_position_test: Failed to set altitude while setting global position of viewport. "
                  f"Expected {c1.alt}, received {vp1.get_absolute_altitude()}")
        return t1 and t2
    except Exception as e:
        print(f"set_global_position_test: Exception {e} thrown")
        return False
    
def adjust_global_position_test():
    try:
        vp1 = Viewport(tc, 0, 0)
        c1 = Coordinate(1.0, 2.0, 3.0)
        vp1.adjust_global_position(c1, 1)
        t1 = (vp1.get_global_position() == c1)
        if not t1:
            print(f"adjust_global_position_test: Failed to adjust global position along coordinate vector with timestep 1. "
                  f"Expected {c1}, resulted in {vp1.get_global_position()}")
        vp1.set_global_position(tc)
        vp1.adjust_global_position(c1, 0.1)
        t2 = (vp1.get_global_position() == Coordinate(0.1, 0.2, 0.3))
        if not t2:
            print(f"adjust_global_position_test: Failed to adjust global position along coordinate vector with fractional timestep. "
                  f"Expected {Coordinate(.1, .2, .3)}, resulted in {vp1.get_global_position()}")
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
        t1 = (vp1.horizontal_fov == 69.28203)
        if not t1:
            print(f"derive_hfov_test: Failed to calculate horizontal FOV from vertical and diagonal. "
                  f"Expected 69.282, resulted in {vp1.horizontal_fov}")
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
        t1 = (vp1.vertical_fov == 69.28203)
        if not t1:
            print(f"derive_vfov_test: Failed to calculate vertical FOV from horizontal and diagonal. "
                  f"Expected 69.282, resulted in {vp1.vertical_fov}")
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
        t1 = (vp1.diagonal_fov == 72.11103)
        if not t1:
            print(f"derive_dfov_test: Failed to calculate diagonal FOV from horizontal and vertical. "
                  f"Expected 72.111, resulted in {vp1.diagonal_fov}")
        return t1
    except Exception as e:
        print(f"derive_dfov_test: Exception {e} thrown")
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
    print(f"Test Results. {successes} / {test_ctr} cases passed.")
    if len(failure_list) != 0:
        print("Failed test cases:")
        for entries in failure_list:
            print(f"    Test ID: {entries[0]} - Test Name: {entries[1]}")
    print()

if __name__ == "__main__":
    main()