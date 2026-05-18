package util

import (
    "os"
    "net"
    "fmt"
    "syscall"
	
	"github.com/google/uuid"
    "github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

func CreateSocketPairFiles() (*os.File, *os.File, error) {
	// Create a socket pair to communicate with the plugin
	fds, err := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	if err != nil {
		log.Error().Err(err).Msg("couldn't open socket pair")
		return nil, nil, err
	}

	// Create internal files
    id := uuid.New().String()
	ln := os.NewFile(uintptr(fds[0]), fmt.Sprintf("listened-%s", id))
	client := os.NewFile(uintptr(fds[1]), fmt.Sprintf("client-%s", id))
    return ln, client, nil
}

func CreateEndpoints(code AuthCode, lnFile, clientFile *os.File) (net.Listener, *grpc.ClientConn, error) {
	// Build the file connections
	lnConn, err := net.FileConn(lnFile)
	if err != nil {
		log.Error().Err(err).Msg("couldn't open listener socket")
		return nil, nil, err
	}
	clientConn, err := net.FileConn(clientFile)
	if err != nil {
		log.Error().Err(err).Msg("couldn't open client socket")
		return nil, nil, err
	}
	spClient, err := NewSocketPairClient(clientConn)
	if err != nil {
		log.Error().Msg("couldn't create socket pair client")
		return nil, nil, err
	}

	return NewSocketPairListener(lnConn, code), spClient, nil
}
