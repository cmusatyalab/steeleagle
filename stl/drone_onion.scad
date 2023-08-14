// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

$fa = 1;
$fs = 0.4;

tol = 0.2;

onion_width = 50;
onion_height = 80;
onion_depth = 11;

wall = 2;

module onion(w, h, d) {
    cutout = d+2;
    difference() {
        // main shape
        translate([-tol, -tol, 0])
        cube([w+2*tol, h+2*tol, cutout]);
        // mounting holes
        post = 3 - tol;
        translate([2.5, h-6.5, -1]) cylinder(h=d, d=post);
        translate([2.5, 13, -1]) cylinder(h=d, d=post);
        translate([w-12, h-35, -1]) cylinder(h=d, d=post);

        // fillet at top
        translate([0, -wall, d-1])
        union() {
            translate([-tol, 0, 0])
            rotate([0, -45, 0])
            cube([4, h+wall*3, 4]);
            translate([w+tol, 0, 0])
            rotate([0, -45, 0])
            cube([4, h+wall*3, 4]);
        }
    }
    // reset button
    translate([-2, 43.5, 1]) cube([3, 5.5, cutout]);
    // usb port
    translate([-2, 32, 1]) cube([3, 10, cutout]);
    // power switch
    translate([-2, 16, 1]) cube([3, 10, cutout]);
    // battery
    translate([1, -2, 1]) cube([10, 3, cutout]);
    // coax 1
    translate([15.5, -2, 1]) cube([5, 3, cutout]);
    // coax 2
    translate([35.5, -2, 1]) cube([5, 3, cutout]);
    // sim
    translate([22, 60+wall, -wall]) cube([15, 20, wall+tol]);
    // header
    translate([43.5, 77.8, 1]) cube([5.5, 3, cutout]);
    // remove fragile pillar between usb and reset
    translate([-2, 41, 1]) cube([3, 3, cutout]);

    // bottom cutouts

    // originally one big hole, but added a strip to mount reversed
    //translate([5, 9, -3]) cube([40, 32, 5]);
    translate([5, 9, -3]) cube([40, 16, 5]);
    translate([5, 30, -3]) cube([40, 11, 5]);

    translate([5, 5, -3]) cube([34, 5, 5]);
    translate([5, 55, -3]) cube([40, 20, 5]);
    translate([5, 43, -3]) cube([30, 6, 5]);  // resistors
    translate([41, 2, -3]) cube([9, 5, 5]);   // vreg
}

module case() {
    difference() {
        cube([onion_width+wall, onion_height+wall, onion_depth+1+tol]);
        translate([wall/2, wall/2, wall/2])
        onion(w=onion_width, h=onion_height, d=onion_depth);
    }
}

module lid() {
    cube([onion_width+wall, onion_height+wall, wall/4]);
    difference() {
        translate([wall/2, wall/2, 0])
        cube([onion_width, onion_height, wall]);
        translate([wall*2, wall, wall/4])
        cube([onion_width-wall*3, onion_height-wall, wall+1]);

        // fillet
        translate([0, -wall, 0])
        union() {
            translate([wall/2, 0, wall])
            rotate([0, -135, 0])
            translate([-4, 0, 0])
            cube([4, onion_height+wall*3, 4]);
            translate([onion_width+wall/2, 0, wall])
            rotate([0, 135, 0])
            cube([4, onion_height+wall*3, 4]);
        }
    }
}

case();
//lid();
