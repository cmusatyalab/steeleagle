package protos

import _ "embed"

//go:embed protos.desc
var DescriptorFile []byte // Descriptor file containing protocol file descriptor set
