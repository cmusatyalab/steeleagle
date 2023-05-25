#!/bin/bash
#To be run in openscout-vol after each flight
#Zips all images from the engines and then removes them from the filesystem
find . -name "*.jpg" -print | zip engine-images -@
find . -name "*.jpg" -type f -delete

