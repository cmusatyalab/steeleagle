$fa = 1;
$fs = 0.4;

battery_width = 45;
battery_height = 50;
collar_width = 28;
clip_width = 30;
clip_depth = 7;
neck_length = 37.6;
wall_thickness = 4;

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

module collar(battery_width, battery_height, collar_width, wall_thickness) {
    linear_extrude(collar_width) {
        intersection() {
            square([battery_width+wall_thickness*2, battery_height+wall_thickness*2+2], center=true);
            difference() {
                offset(r=wall_thickness)
                battery_shape(battery_width, battery_height);
                battery_shape(battery_width, battery_height);
            };
        };
    };
}

module neck(battery_width, battery_height, collar_width, clip_width, neck_length, wall_thickness) {
    linear_extrude(neck_length+collar_width+6) {
        offset(r=1) offset(delta=-1)
        difference() {
            translate([-clip_width/2, battery_height/2, 0])
            square([clip_width, wall_thickness+1]);
            battery_shape(battery_width, battery_height);
        }
    }
}

module clip(battery_height, collar_width, clip_width, clip_depth, neck_length, wall_thickness, r=3) {
    //color("#0f0")
    translate([0, battery_height/2+wall_thickness, neck_length+collar_width+r])
    rotate([90, 0, 0])
    difference() {
        hull() {
            translate([-clip_width/2, 0, 0])
            cube([clip_width, r, clip_depth]);
            translate([r-clip_width/2, 0, 0])
            cylinder(h=clip_depth+wall_thickness, r=r);
            translate([clip_width/2-r, 0, 0])
            cylinder(h=clip_depth+wall_thickness, r=r);
        }
        translate([0, 0, wall_thickness+5.5])
        rotate([33.69, 0, 0])
        translate([0, 5, 0])
        cube([battery_width, 10, 20], center=true);
    }
}

module gap(battery_width, clip_width, collar_width, wall_thickness, offset) {
    gap_width = (battery_width - clip_width) / 2;
    translate([offset*(gap_width+clip_width)/2, battery_height/2+(wall_thickness+2), collar_width/2])
    rotate([90, 0, 0])
    union() {
        cylinder(h=wall_thickness+4, d=gap_width);
        translate([-gap_width/2, 0, 0])
        cube([gap_width, collar_width, wall_thickness+4]);
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
    battery_width=battery_width,
    battery_height=battery_height,
    clip_width=clip_width,
    clip_depth=clip_depth,
    collar_width=collar_width,
    neck_length=neck_length,
    wall_thickness=wall_thickness,
    hole_width=15
) {
    difference() {
        union() {
            collar(battery_width, battery_height, collar_width, wall_thickness);
            neck(battery_width, battery_height, collar_width, clip_width, neck_length, wall_thickness);
            clip(battery_height, collar_width, clip_width, clip_depth, neck_length, wall_thickness);
        }

        // fan hole
        translate([0, -battery_height/2-2, collar_width/2])
        rotate([90, 0, 0])
        hole(wall_thickness, hole_width);

        // hole in neck
        translate([0, battery_height/2+3, collar_width])
        rotate([90, 90, 0])
        hole(wall_thickness, hole_width, hole_length=neck_length);

        // gaps next to neck
        gap(battery_width, clip_width, collar_width, wall_thickness, -1);
        gap(battery_width, clip_width, collar_width, wall_thickness, 1);

        // side holes
        translate([battery_width/2+2, 0, collar_width/2])
        rotate([90, 0, 90])
        hole(wall_thickness, hole_width);

        translate([-battery_width/2-2, 0, collar_width/2])
        rotate([90, 0, 90])
        hole(wall_thickness, hole_width);
    };
}

//example();

drone_body_mount();

//example();
