package policy

default allowed := false
default next_state := ""
default debug := ""

allowed if {
    command := sprintf("%v.%v", input.peer, input.command)
    glob.match(input.law[input.state].allowed[_], [], command)
}

allowed if {
    input.peer == "server"
    input.peer == "kernel"
}

next_state := state if {
    command := sprintf("%v.%v", input.peer, input.command)
    glob.match(input.law[input.state].allowed[_], [], command)
    transition := input.law[input.state].match[_]
    glob.match(transition[0], [], command)
    state := transition[1]
}
