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

module battery_shape() {
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

module collar(hole_radius=7.5) {
    linear_extrude(collar_width) {
        intersection() {
            square([battery_width+wall_thickness*2, battery_height+wall_thickness*2+2], center=true);
            difference() {
                offset(r=wall_thickness)
                battery_shape();
                battery_shape();
            };
        };
    };
}

module collar_with_fanhole(hole_width=15) {
    hole_radius = hole_width/2;
    difference() {
        collar();
        translate([0, 0, collar_width/2-0.5])
        rotate([90, 0, 0])
        hull() {
            translate([-3-hole_radius, 0, 0])
            cylinder(50, hole_radius, hole_radius);
            translate([hole_radius+3, 0, 0])
            cylinder(50, hole_radius, hole_radius);
        };
    };
}
        

module neck() {
    linear_extrude(neck_length+collar_width+6) {
        offset(r=1) offset(delta=-1)
        difference() {
            translate([-clip_width/2, battery_height/2, 0])
            square([clip_width,wall_thickness+1]);
            battery_shape();
        }
    }
}

module clip(r=3) {
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

//example();
//collar_with_fanhole();
collar();
neck();
clip();
//example();

module stretched_hole_mask(hole_width=15, hole_length=30) {
    r=hole_width/2;
    s=hole_length-hole_width;
    translate([0, 0, 2])
    difference() {
        union() { 
            translate([-s/2, 0, 0])
            cylinder(h=4, r=r, center=true);
            translate([s/2, 0, 0])
            cylinder(h=4, r=r, center=true);
            cube([s, hole_width, 4], center=true);
            
            translate([-s/2, 0, -1.5])
            cylinder(h=3, r=r+2, center=true);
            translate([s/2, 0, -1.5])
            cylinder(h=3, r=r+2, center=true);
            translate([0, 0, -1.5])
            cube([s, hole_width+4, 3], center=true);
        }
   
        translate([-s/2, 0, 0])
        rotate([0, 0, 90])
        rotate_extrude(angle=180)
          translate([r+2, 0, 0])
          circle(2);
        translate([s/2, 0, 0])
        rotate([0, 0, -90])
        rotate_extrude(angle=180)
          translate([r+2, 0, 0])
          circle(2);
        translate([0, -(r+2), 0])
        rotate([0, 90, 0])
        cylinder(h=s+2, r=2, center=true);
        translate([0, r+2, 0])
        rotate([0, 90, 0])
        cylinder(h=s+2, r=2, center=true);
    }
}

//stretched_hole_mask();
