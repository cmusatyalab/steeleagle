#!/bin/bash
if [[ $# -ne 3 ]]; then
   printf "Usage: java2dex.sh javac_path d8_path androidjar_path \n"
   exit 1;
fi

javac="$1"
d8="$2"
sdk="$3"
#class="$4"

"${javac}" edu/cmu/cs/dronebrain/FlightScript.java
"${d8}" edu/cmu/cs/dronebrain/FlightScript.class --lib "${sdk}"

