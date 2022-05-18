#!/bin/bash
args=$*
./main.py $args &
./command.py $args &
#./compute.py $args
