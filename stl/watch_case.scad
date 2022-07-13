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

module thread_chamfer(rot, tilt, od, watch, wall) {
    rotate([0, 0, rot])
    translate([0, od/2, 0])
    rotate([0, 0, tilt])
    translate([-5, 0, wall])
    cube([10, 4, watch]);
}


module watch_case(watch_diameter=44, watch_thickness=10, wall_thickness=3, thread_depth=1) {
    id = watch_diameter + 2;
    od = id + 2 * wall_thickness;
    td = od + 2 * thread_depth;
    height = watch_thickness + wall_thickness;

    difference () {
        generic_bottle_neck(
            id=id,
            neck_d=od,
            thread_od=td,
            height=height,
            support_d=0
        );

        // openings for watch-band arms
        translate([18/2, -(td+2)/2, -1])
        cube([7, td+2, height+2]);
        rotate([0, 0, 180])
        translate([18/2, -(td+2)/2, -1])
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
        thread_chamfer(rot=42, tilt=-25, od=od, watch=watch_thickness, wall=wall_thickness);
        thread_chamfer(rot=222, tilt=-25, od=od, watch=watch_thickness, wall=wall_thickness);
        thread_chamfer(rot=-42, tilt=25, od=od, watch=watch_thickness, wall=wall_thickness);
        thread_chamfer(rot=-222, tilt=25, od=od, watch=watch_thickness, wall=wall_thickness);
    }
    cylinder(h=wall_thickness, d=od);
}

module watch_cap(watch_diameter=44, watch_thickness=10, wall_thickness=3, thread_depth=1) {
    id = watch_diameter + 2;
    od = id + 2 * wall_thickness;
    td = od + 2 * thread_depth;

    difference () {
        generic_bottle_cap(
            wall=1,
            texture="knurled",
            height=watch_thickness,
            thread_od=td,
            neck_od=od,
            tolerance=0.2
        );

        translate([0, 0, -1])
        cylinder(h=3, d=watch_diameter);
    }
}

//watch_case(watch_diameter=watch_diameter, watch_thickness=watch_thickness);
//watch_cap(watch_diameter=watch_diameter, watch_thickness=watch_thickness);

//example_watch_case();
