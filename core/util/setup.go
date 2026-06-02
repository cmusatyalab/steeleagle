package util

import (
	"fmt"
	"net"
	"os"
	"syscall"

	"github.com/google/uuid"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
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
	inner := os.NewFile(uintptr(fds[0]), fmt.Sprintf("inner-%s", id))
	outer := os.NewFile(uintptr(fds[1]), fmt.Sprintf("outer-%s", id))
	return inner, outer, nil
}

func CreateSocketPairEndpoints(code AuthCode, lnFile, clientFile *os.File) (net.Listener, *grpc.ClientConn, error) {
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

	return NewSocketPairCodedListener(lnConn, code), spClient, nil
}

func CreateAbstractSocketEndpoints(code AuthCode, pid int, lnid, cid string) (net.Listener, *grpc.ClientConn, error) {
    // Listen on the server abstract socket
	ln, err := net.Listen("unix", fmt.Sprintf("@%s", lnid))
	if err != nil {
		log.Error().Err(err).Msg("couldn't listen on abstract socket")
		return nil, nil, err
	}

	// Connect to the client abstract socket
    target := fmt.Sprintf("unix-abstract:%s", cid)
    client, err := grpc.NewClient(
		target,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		log.Error().Err(err).Msg("couldn't connect client to abstract socket")
		ln.Close()
		return nil, nil, err
	}

    acl := GetACL([]string{}, []int{pid})
	return NewCodedListener(ln, code, acl), client, nil
}
