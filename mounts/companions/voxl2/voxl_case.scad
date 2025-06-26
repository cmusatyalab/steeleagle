// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

$fa = 1;
$fs = 0.4;

tol = 0.2;

voxl_width = 38;
voxl_length = 72.5; //86
voxl_height = 40.5;
pedestal_height = 25.5;
post_height = 2;

wall = 2;

module voxl(w, h, d) {
    cutout = d+2;
    difference() {
        // main shape
        translate([-tol, -tol, 0])
        cube([w+2*tol, h+2*tol, cutout]);
        // mounting holes
        post = 2.6 - tol;

        //translate([1.75, h-6, -1]) cylinder(h=post_height, d=post);
        //translate([1.75, 4, -1]) cylinder(h=post_height, d=post);
        //translate([w-1.75, h-6, -1]) cylinder(h=post_height, d=post);
        //translate([w-1.75, 4, -1]) cylinder(h=post_height, d=post);
        translate([0, h-8, -1]) cube([4,8,pedestal_height]) ;
        translate([0, h-8, -1]) cube([8,8,pedestal_height/3]) ;
        translate([1.75, h-4.75, pedestal_height-1]) cylinder(h=post_height, d=post);

        translate([0, 4, -1]) cube([6,6,pedestal_height]);
        translate([1.75, 5.75, pedestal_height-1]) cylinder(h=post_height, d=post);

        translate([w-4, h-8, -1]) cube([4,8,pedestal_height]);
        translate([w-8, h-8, -1]) cube([8,8,pedestal_height/3]);
        translate([w-1.75, h-4.75, pedestal_height-1]) cylinder(h=post_height, d=post);

        translate([w-6, 4, -1]) cube([6,6,pedestal_height]);
        translate([w-1.75, 5.75, pedestal_height-1]) cylinder(h=post_height, d=post);
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
    // battery slot
    translate([10, -2, 0]) cube([17, 5.5, 25]);
    // notch for battery cable
    translate([27, -2, 0]) cube([4, 5.5, 8]);
    // usb cable for wifi adapter
    translate([-2, 42, 30]) cube([5.5, 16, 11]);
    // holes for weight reduction and airflow
//    translate([-3, 62, 25]) sphere(r=4);
//    translate([-3, 62, 15]) sphere(r=4);
//    translate([-3, 62, 5]) sphere(r=4);
//
//    translate([-3, 52, 25]) sphere(r=4);
//    translate([-3, 52, 15]) sphere(r=4);
//    translate([-3, 52, 5]) sphere(r=4);
//
//    translate([-3, 42, 25]) sphere(r=4);
//    translate([-3, 42, 15]) sphere(r=4);
//    translate([-3, 42, 5]) sphere(r=4);
//
//    translate([-3, 32, 35]) sphere(r=4);
//    translate([-3, 32, 25]) sphere(r=4);
//    translate([-3, 32, 15]) sphere(r=4);
//    translate([-3, 32, 5]) sphere(r=4);
//    translate([-3, 22, 35]) sphere(r=4);
//    translate([-3, 22, 25]) sphere(r=4);
//    translate([-3, 22, 15]) sphere(r=4);
//    translate([-3, 22, 5]) sphere(r=4);
//    translate([-3, 12, 35]) sphere(r=4);
//    translate([-3, 12, 25]) sphere(r=4);
//    translate([-3, 12, 15]) sphere(r=4);
//    translate([-3, 12, 5]) sphere(r=4);


//    translate([40, 62, 25]) sphere(r=4);
//    translate([40, 62, 15]) sphere(r=4);
//    translate([40, 62, 5]) sphere(r=4);
//    translate([40, 52, 25]) sphere(r=4);
//    translate([40, 52, 15]) sphere(r=4);
//    translate([40, 52, 5]) sphere(r=4);
//    translate([40, 42, 35]) sphere(r=4);
//    translate([40, 42, 25]) sphere(r=4);
//    translate([40, 42, 15]) sphere(r=4);
//    translate([40, 42, 5]) sphere(r=4);
//    translate([40, 32, 35]) sphere(r=4);
//    translate([40, 32, 25]) sphere(r=4);
//    translate([40, 32, 15]) sphere(r=4);
//    translate([40, 32, 5]) sphere(r=4);
//    translate([40, 22, 35]) sphere(r=4);
//    translate([40, 22, 25]) sphere(r=4);
//    translate([40, 22, 15]) sphere(r=4);
//    translate([40, 22, 5]) sphere(r=4);
//    translate([40, 12, 35]) sphere(r=4);
//    translate([40, 12, 25]) sphere(r=4);
//    translate([40, 12, 15]) sphere(r=4);
//    translate([40, 12, 5]) sphere(r=4);
    // antenna window #1
    translate([35, 56, 30]) cube([5.5, 11, 11]);
    // antenna window #2
    translate([28, voxl_length, 33]) cube([8, 5.5, 8]);
    //power/usbc window
    translate([4, voxl_length, 20]) cube([28, 5.5, 11]);
}

module case() {
    difference() {
        cube([voxl_width+wall, voxl_length+wall, voxl_height+1+tol]);
        translate([wall/2, wall/2, wall/2])
        voxl(w=voxl_width, h=voxl_length, d=voxl_height);
    }
}

module lid() {
    cube([voxl_width+wall, voxl_length+wall, wall/4]);
    difference() {
        translate([wall/2, wall/2, 0])
        cube([voxl_width, voxl_length, wall]);
        translate([wall*2, wall, wall/4])
        cube([voxl_width-wall*3, voxl_length-wall, wall+1]);

        // fillet
        translate([0, -wall, 0])
        union() {
            translate([wall/2, 0, wall])
            rotate([0, -135, 0])
            translate([-4, 0, 0])
            cube([4, voxl_length+wall*3, 4]);
            translate([voxl_width+wall/2, 0, wall])
            rotate([0, 135, 0])
            cube([4, voxl_length+wall*3, 4]);
        }
    }
}

case();
//lid();
