package main

import (
    "flag"
)

var (
    name = flag.String("name", "", "vehicle name (required)")
    sandbox_mission = flag.Bool("sandbox-mission", false, "whether or not to sandbox the mission module (default: false)")
    sandbox_driver = flag.Bool("sandbox-driver", false, "whether or not to sandbox the driver module (default: false)")
)

func main() {
    flag.Parse()
}
