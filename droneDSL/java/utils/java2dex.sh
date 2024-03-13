#!/bin/bash

# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

d8="$D8_PATH"
sdk="$SDK_PATH"
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

