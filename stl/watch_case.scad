$fa = 1;
$fs = 0.4;

module example_watch_case() {
    color(c=[0, 0, 1, 0.5])
    translate([-27, 28, 0])
    rotate([90, 0, 0])
    import("watch_case.stl");
}

//example_watch_case();

include <BOSL2/std.scad>
include <BOSL2/bottlecaps.scad>

watch_diameter = 40;
watch_thickness = 10;
//watch_thickness = 9.8;

module thread_chamfer(rot, tilt, od, watch, floor) {
    rotate([0, 0, rot])
    translate([0, od/2, 0])
    rotate([0, 0, tilt])
    translate([-5, 0, floor])
    cube([10, 4, watch]);
}

function outer_diameter(watch_diameter, arm_length=6, arm_width=24) =
    let (x = watch_diameter + arm_length)
    let (y = arm_width + 1)
    sqrt(x*x + y*y);


module watch_case(watch_diameter=44, watch_thickness=10, floor_thickness=1, thread_depth=1) {
    id = watch_diameter + 2;
    od = outer_diameter(watch_diameter);
    td = od + 2 * thread_depth;
    height = watch_thickness + floor_thickness;

    difference () {
        generic_bottle_neck(
            id=id,
            neck_d=od,
            thread_od=td,
            height=height,
            support_d=0
        );

        // openings for watch-band arms
        translate([19/2, -(td+2)/2, -1])
        cube([7, td+2, height+2]);
        rotate([0, 0, 180])
        translate([19/2, -(td+2)/2, -1])
        cube([7, td+2, height+2]);

        // clear space for watch buttons
        intersection () {
            translate([0, 0, -1])
            cylinder(h=height+2, d=id+2);

            union () {
                rotate([0, 0, 65])
                translate([-6, -(td+2)/2])
                cube([12, td+2, height+2]);

                rotate([0, 0, -65])
                translate([-6, -(td+2)/2])
                cube([12, td+2, height+2]);
            }
        }

        // clip pointy bits off threads
        thread_chamfer(rot=42, tilt=-25, od=od, watch=watch_thickness, floor=floor_thickness);
        thread_chamfer(rot=222, tilt=-25, od=od, watch=watch_thickness, floor=floor_thickness);
        thread_chamfer(rot=-42, tilt=25, od=od, watch=watch_thickness, floor=floor_thickness);
        thread_chamfer(rot=-222, tilt=25, od=od, watch=watch_thickness, floor=floor_thickness);
    }
    cylinder(h=floor_thickness, d=od);
}

module watch_cap(watch_diameter=44, watch_thickness=10, thread_depth=1) {
    od = outer_diameter(watch_diameter);
    td = od + 2 * thread_depth;
    wall = 0.5;

    difference () {
        generic_bottle_cap(
            wall=wall,
            //texture="knurled",
            height=watch_thickness,
            thread_od=td,
            neck_od=od,
            tolerance=0.2
        );

        // punch hole for watch face
        translate([0, 0, -1])
        cylinder(h=wall+2, d=watch_diameter);
    }
}

//watch_case(watch_diameter=watch_diameter, watch_thickness=watch_thickness);
//watch_cap(watch_diameter=watch_diameter, watch_thickness=watch_thickness);

//example_watch_case();
