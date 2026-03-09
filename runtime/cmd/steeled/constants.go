package main

import _ "embed"

//go:embed defaults/config.toml
var DefaultConfig []byte // Default daemon configuration file
