$fa = 1;
$fs = 0.4;

battery_width = 45;
battery_height = 50;
neck_length = 37.7;

watch_diameter = 40;
watch_thickness = 10;

collar_width = 28;
wall_thickness = 4;

include <body_clip.scad>
include <watch_case.scad>

translate([-60, 0, 0])
watch_case(watch_diameter=watch_diameter, watch_thickness=watch_thickness);
translate([60, 0, 0])
watch_cap(watch_diameter=watch_diameter, watch_thickness=watch_thickness);
