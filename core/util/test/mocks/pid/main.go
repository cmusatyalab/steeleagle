package main

import (
	"fmt"
	"os"
	"time"
    "net"
)

// connClosed tries to dial the listener and returns true if it is closed,
// otherwise false.
func connClosed() bool {
    time.Sleep(100 * time.Millisecond) // need to wait to make sure the server is ready
    conn, err := net.Dial("unix", "/tmp/listener.sock")
    if err != nil {
        fmt.Printf("pid_test: got error when trying to dial: %v\n", err)
        return true
    }
	conn.SetReadDeadline(time.Now().Add(200 * time.Millisecond))
	_, err = conn.Read(make([]byte, 1))
	if err == nil {
		return false
	}
	if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
		return false
	}
    fmt.Println("pid_test: read went through")
	return true
}

// main delegates to connClosed.
func main() {
	if out := connClosed(); out {
        fmt.Println("pid_test: connection closed")
		os.Exit(1)
	}
}
