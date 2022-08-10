include <body_clip.scad>
include <watch_case.scad>

$fa = 1;
$fs = 0.4;

battery_width = 45;
battery_height = 50;
neck_length = 37.7;

watch_diameter = 40;
watch_thickness = 10;

collar_width = 28;
wall_thickness = 4;

drone_body_mount(
    battery_width=battery_width,
    battery_height=battery_height,
    neck_length=neck_length,
    collar_width=collar_width,
    wall_thickness=wall_thickness,
    holes="everywhere"
);

translate([0, battery_width/2+wall_thickness+1, neck_length+collar_width]) rotate([-90, 0, 0])
watch_case(watch_diameter=watch_diameter, watch_thickness=watch_thickness);
