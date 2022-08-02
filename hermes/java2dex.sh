#!/bin/bash
if [[ $# -ne 3 ]]; then
   printf "Usage: java2dex.sh javac_path d8_path androidjar_path \n"
   exit 1;
fi

javac="$1"
d8="$2"
sdk="$3"
#class="$4"
cd src
"${javac}" -verbose edu/cmu/cs/dronebrain/MS.java
if [ $? -eq 0 ] 
then 
  echo "java2dex.sh: Compiled with javac. Attempting to dex..."
else 
  echo "java2dex.sh: Compilation with javac failed!"
  exit 1;
fi
"${d8}" edu/cmu/cs/dronebrain/MS.class --lib "${sdk}"
if [ $? -eq 0 ] 
then 
  echo "java2dex.sh: Built dex with d8."
else 
  echo "java2dex.sh: Dexing failed!"
  exit 1;
fi

