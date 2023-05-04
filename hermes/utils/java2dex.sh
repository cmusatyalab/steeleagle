#!/bin/bash

# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

if [[ $# -ne 3 ]]; then
   printf "Usage: java2dex.sh javac_path d8_path androidjar_path \n"
   exit 1;
fi

javac="$1"
d8="$2"
sdk="$3"
#class="$4"
./gradlew uberJar
if [ $? -eq 0 ] 
then 
  echo "java2dex.sh: Compiled with gradlew. Attempting to dex..."
else 
  echo "java2dex.sh: Compilation with gradlew failed!"
  exit 1;
fi
"${d8}" ./app/build/libs/app-uber.jar --lib "${sdk}" --output .
if [ $? -eq 0 ] 
then 
  echo "java2dex.sh: Built dex with d8."
else 
  echo "java2dex.sh: Dexing failed!"
  exit 1;
fi

