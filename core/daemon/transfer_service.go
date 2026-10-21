package daemon

import (
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TransferFile transfers a file to the daemon's files directory.
func (d *Daemon) TransferFile(
	stream grpc.BidiStreamingServer[daemonpb.TransferFileRequest, daemonpb.TransferFileResponse],
) error {
	// TODO: implement
	return status.Error(codes.Unimplemented, "TransferFile not implemented")
}

// TransferModel transfers a model to the daemon's models directory.
func (d *Daemon) TransferModel(
	stream grpc.BidiStreamingServer[daemonpb.TransferModelRequest, daemonpb.TransferModelResponse],
) error {
	// TODO: implement
	return status.Error(codes.Unimplemented, "TransferModel not implemented")
}
