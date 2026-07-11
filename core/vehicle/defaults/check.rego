package policy

import rego.v1

default allowed := false

allowed if {
    startswith(input.command, "server/")
}

allowed if {
    startswith(input.command, "admin/")
}

allowed if {
    some i
    glob.match(input.law[input.state].allowed[i], [], input.command)
}

default next_state := ""

next_state := transition[1] if {
    allowed
    some i
    transition := input.law[input.state].match[i]
    count(transition) == 2
    glob.match(transition[0], [], input.command)
    _ = input.law[transition[1]]
}
