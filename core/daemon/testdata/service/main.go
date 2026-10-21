// Command service is a fake plugin that serves on its listen socket, so the
// daemon can connect to it, then calls the daemon through its client socket
// and records the status code of each call in the file given as its argument.
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

func main() {
	if err := run(os.Args[1]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	// Run until killed, like a real plugin
	select {}
}

func run(out string) error {
	// Plugins that host a service are only started once their socket exists
	if sock := os.Getenv("LISTEN_SOCKET"); sock != "" {
		ln, err := net.Listen("unix", sock)
		if err != nil {
			return err
		}
		go grpc.NewServer().Serve(ln)
	}

	conn, err := grpc.NewClient("unix://"+os.Getenv("CLIENT_SOCKET"),
		grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return err
	}
	defer conn.Close()
	client := daemonpb.NewDaemonServiceClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// A read the daemon law allows for external callers, and a write it only
	// allows for privileged ones; an allowed install fails on its empty url
	_, listErr := client.ListServices(ctx, &daemonpb.ListServicesRequest{})
	_, installErr := client.InstallPackage(ctx, &daemonpb.InstallPackageRequest{})
	calls := fmt.Sprintf("list=%s\ninstall=%s\n", status.Code(listErr), status.Code(installErr))
	return os.WriteFile(out, []byte(calls), 0644)
}
