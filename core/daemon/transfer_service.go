package daemon

import (
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/download"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TransferFile transfers a file to the daemon's files directory.
func (d *Daemon) TransferFile(
	stream grpc.BidiStreamingServer[daemonpb.TransferFileRequest, daemonpb.TransferFileResponse],
) error {
	dir, err := util.GetFileDir()
	if err != nil {
		return status.Errorf(codes.Internal, "could not get files directory: %v", err)
	}
	return download.DownloadFile(d.log, stream, dir, func(number int32) *daemonpb.TransferFileResponse {
		return daemonpb.TransferFileResponse_builder{Received: number}.Build()
	})
}

// TransferModel transfers a model to the daemon's models directory.
func (d *Daemon) TransferModel(
	stream grpc.BidiStreamingServer[daemonpb.TransferModelRequest, daemonpb.TransferModelResponse],
) error {
	dir, err := util.GetModelDir()
	if err != nil {
		return status.Errorf(codes.Internal, "could not get models directory: %v", err)
	}
	return download.DownloadFile(d.log, stream, dir, func(number int32) *daemonpb.TransferModelResponse {
		return daemonpb.TransferModelResponse_builder{Received: number}.Build()
	})
}
