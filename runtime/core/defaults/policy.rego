package policy

import rego.v1

default allowed := false

allowed if {
    startswith(input.command, "server/")
}

allowed if {
    startswith(input.command, "kernel/")
}

allowed if {
    some i
    glob.match(input.law[input.state].allowed[i], [], input.command)
}

default next_state := ""

next_state := transition[1] if {
    some i, j, k
    glob.match(input.law[input.state].allowed[i], [], input.command)
    transition := input.law[input.state].match[j]
    count(transition) == 2
    glob.match(transition[0], [], input.command)
    input.law[k] == transition[1]
}   
