$fa = 1;
$fs = 0.4;

module example() {
    color(c=[0, 0, 1, 0.5])
    translate([0, 30, -27.9])
    rotate([90, 0, 0])
    import("body_clip.stl");
}

module battery_shape(battery_width, battery_height) {
    offset(r=2) {
        square([battery_width-4, battery_height-4], center=true);
        intersection() {
            translate([0, 0.2-battery_height/2, 0])
            circle(r=battery_height);
            translate([0, 3, 0])
            square([battery_width-4, battery_height-4], center=true);
        }
    }
}

module collar_and_neck(battery_width, battery_height, neck_length, collar_width, clip_width, clip_depth, wall_thickness) {
    clip_thickness = 4;
    width = battery_width + wall_thickness*2;
    height = battery_height + wall_thickness*2 + 2;
    neck_height = collar_width + neck_length + clip_thickness;
    clip_height=clip_depth+wall_thickness+2;

    difference() {
        union() {
            // collar
            translate([0, 1, collar_width/2])
            cube([width, height, collar_width], center=true);
            // neck
            translate([-clip_width/2, battery_height/2, 0])
            cube([clip_width, wall_thickness+2, neck_height]);
        }

        translate([0, 0, -1]) linear_extrude(neck_height) {
            battery_shape(battery_width, battery_height);
        };
    }

    // clip
    r = clip_thickness/2;
    translate([0, battery_height/2+wall_thickness+2, neck_height-r])
    rotate([90, 0, 0])
    difference() {
        union() {
            translate([r-clip_width/2, -r, 0])
            cube([clip_width-2*r, r, clip_height]);
            translate([-clip_width/2, 0, 0])
            cube([clip_width, r, clip_height]);
            translate([r-clip_width/2, 0, 0])
            cylinder(h=clip_height, r=r);
            translate([clip_width/2-r, 0, 0])
            cylinder(h=clip_height, r=r);
        }
        translate([0, 0, wall_thickness+5.5])
        rotate([33.69, 0, 0])
        translate([0, 6, 0])
        cube([battery_width, 10, 20], center=true);
    }
}

module gap(battery_width, clip_width, collar_width, wall_thickness, offset) {
    gap_width = (battery_width - clip_width) / 2;
    translate([offset*(gap_width+clip_width)/2, battery_height/2+wall_thickness*2+2, collar_width/2])
    rotate([90, 0, 0])
    union() {
        cylinder(h=wall_thickness+6, d=gap_width);
        translate([-gap_width/2, 0, 0])
        cube([gap_width, collar_width, wall_thickness+6]);
    }
}

module hole(wall_thickness, hole_width, hole_length=36) {
    coff=(hole_length-hole_width)/2;
    translate([-coff, 0, 0])
    cylinder(h=wall_thickness+4, d=hole_width, center=true);
    translate([coff, 0, 0])
    cylinder(h=wall_thickness+4, d=hole_width, center=true);
    cube([hole_length-hole_width, hole_width, wall_thickness+4], center=true);
}

module drone_body_mount(
    battery_width,
    battery_height,
    neck_length,
    clip_width=30,
    clip_depth=7,
    collar_width=28,
    wall_thickness=4,
    hole_width=15,
    holes="minimal"
) {
    translate([0, -(collar_width+neck_length)/2, 0])
    rotate([-90, 0, 0])
    translate([0, -battery_height/2-wall_thickness-2, 0])
    difference() {
        union() {
            collar_and_neck(battery_width, battery_height, neck_length, collar_width, clip_width, clip_depth, wall_thickness);
            //clip(battery_height, neck_length, collar_width, clip_width, clip_depth, wall_thickness);
        }

        // fan hole
        translate([0, -battery_height/2-2, collar_width/2])
        //translate([0, -battery_height/2-2, (collar_width+neck_length+hole_width)/2])
        rotate([90, 0, 0])
        //hole(wall_thickness, collar_width+neck_length-hole_width);
        hole(wall_thickness, hole_width);

        // hole in neck
        if (holes=="neck" || holes=="everywhere") {
            translate([0, battery_height/2+3, collar_width])
            rotate([90, 90, 0])
            hole(wall_thickness, hole_width, hole_length=neck_length);
        }

        // gaps next to neck
        gap(battery_width, clip_width, collar_width, wall_thickness, -1);
        gap(battery_width, clip_width, collar_width, wall_thickness, 1);

        // side holes
        if (holes=="side" || holes=="everywhere") {
            translate([battery_width/2+2, 0, collar_width/2])
            rotate([90, 0, 90])
            hole(wall_thickness, hole_width);

            translate([-battery_width/2-2, 0, collar_width/2])
            rotate([90, 0, 90])
            hole(wall_thickness, hole_width);
        }

        // extreme cut
        translate([0, -7, 0])
        cube([battery_width+10, battery_height, collar_width], center=true);
        translate([0, -hole_width, hole_width/2])
        cube([battery_width+10, battery_height, collar_width], center=true);
    };
}

//example();

battery_width = 45;
battery_height = 50;
neck_length = 37.7;

/*
    holes="neck"
    holes="sides"
    holes="everywhere"
*/
drone_body_mount(battery_width, battery_height, neck_length, holes="everywhere", wall_thickness=1);

//example();
