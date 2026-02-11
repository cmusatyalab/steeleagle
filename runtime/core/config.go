package core

type KernelOption func(*Kernel)

func WithName(name string) func(*Kernel) {
    return func(k *Kernel) {
        k.Name = name
    }
}

func WithPort(port int) func(*Kernel) {
    return func(k *Kernel) {
        k.connections.port = port
    }
}

func WithVPN(vpn bool) func(*Kernel) {
    return func(k *Kernel) {
        k.connections.useVPN = true
    }
}

func WithTest(test bool) func(*Kernel) {
    return func(k *Kernel) {
        k.test = test
    }
}
