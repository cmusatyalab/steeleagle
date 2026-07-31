#!/bin/bash

# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: CC0-1.0
# SPDX-License-Identifier: GPL-2.0-only

args=$*
./main.py $args &
./command.py $args &
