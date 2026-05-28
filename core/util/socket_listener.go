package util

import (
	"fmt"
	"net"
	"sync"
)

type socketPairCodedListener struct {
	// Dummy listener for embedding
	net.Listener
	code   AuthCode
	socket net.Conn
	// Synchronization members for accept loop
	once sync.Once
	done chan struct{}
}

func NewSocketPairCodedListener(sock net.Conn, code AuthCode) net.Listener {
	return &socketPairCodedListener{
		socket: sock,
		code:   code,
		done:   make(chan struct{}),
	}
}

func (l *socketPairCodedListener) Accept() (net.Conn, error) {
	var c net.Conn
	// Return the Connection exactly once to not spawn spurious handlers
	l.once.Do(func() { c = l.socket })
	if c != nil {
		return &Conn{
			Conn: c,
			Addr: &Addr{Addr: c.RemoteAddr(), Code: l.code},
		}, nil
	}
	// Wait until the socket closes, then exit
	<-l.done
	return nil, fmt.Errorf("listener closed")
}

func (l *socketPairCodedListener) Close() error {
	close(l.done)
	return l.socket.Close()
}

func (l *socketPairCodedListener) Addr() net.Addr {
	return l.socket.LocalAddr()
}
