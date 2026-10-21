package daemon

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// chunk is a request of a transfer.
type chunk interface {
	GetChunk() []byte
	GetNumber() int32
	GetTotal() int32
	GetFilename() string
}

// TransferFile transfers a file to the daemon's files directory.
func (d *Daemon) TransferFile(
	stream grpc.BidiStreamingServer[daemonpb.TransferFileRequest, daemonpb.TransferFileResponse],
) error {
	dir, err := util.GetFileDir()
	if err != nil {
		return status.Errorf(codes.Internal, "could not get files directory: %v", err)
	}
	return receiveFile(d.log, stream, dir, func(number int32) *daemonpb.TransferFileResponse {
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
	return receiveFile(d.log, stream, dir, func(number int32) *daemonpb.TransferModelResponse {
		return daemonpb.TransferModelResponse_builder{Received: number}.Build()
	})
}

// receiveFile saves the chunks of a transfer to dir under the file name of the
// first chunk, acknowledging each chunk once it is written.
func receiveFile[Req, Resp any, R interface {
	*Req
	chunk
}](
	log zerolog.Logger,
	stream grpc.BidiStreamingServer[Req, Resp],
	dir string,
	ack func(int32) *Resp,
) error {
	first, err := stream.Recv()
	if errors.Is(err, io.EOF) {
		return status.Error(codes.InvalidArgument, "transfer has no chunks")
	}
	if err != nil {
		return err
	}
	name, total := R(first).GetFilename(), R(first).GetTotal()
	if err := checkFilename(name); err != nil {
		return err
	}
	if total < 1 {
		return status.Errorf(codes.InvalidArgument, "invalid total of %d chunks", total)
	}

	tmp, err := os.CreateTemp(dir, "."+name+".*.part")
	if err != nil {
		return status.Errorf(codes.Internal, "could not create file: %v", err)
	}
	defer func() {
		// The temporary file is only left if the transfer failed
		tmp.Close()
		os.Remove(tmp.Name())
	}()
	req := R(first)
	for number := int32(1); ; number++ {
		if req.GetNumber() != number || req.GetTotal() != total {
			return status.Errorf(codes.InvalidArgument, "expected chunk %d of %d, got chunk %d of %d",
				number, total, req.GetNumber(), req.GetTotal())
		}
		if _, err := tmp.Write(req.GetChunk()); err != nil {
			return status.Errorf(codes.Internal, "could not write chunk %d: %v", number, err)
		}
		if number == total {
			break
		}
		if err := stream.Send(ack(number)); err != nil {
			return err
		}
		next, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			return status.Errorf(codes.InvalidArgument, "transfer ended after chunk %d of %d", number, total)
		}
		if err != nil {
			return err
		}
		req = R(next)
	}

	// Save the file before acknowledging the last chunk, so that a transfer
	// that is acknowledged in full is saved
	if err := tmp.Sync(); err != nil {
		return status.Errorf(codes.Internal, "could not write file: %v", err)
	}
	if err := tmp.Close(); err != nil {
		return status.Errorf(codes.Internal, "could not write file: %v", err)
	}
	path := filepath.Join(dir, name)
	if err := os.Rename(tmp.Name(), path); err != nil {
		return status.Errorf(codes.Internal, "could not save file: %v", err)
	}
	log.Info().Str("path", path).Int32("chunks", total).Msg("transfer saved")
	return stream.Send(ack(total))
}

// checkFilename checks that name is a plain file name, so that a transfer can
// only be saved in its own directory.
func checkFilename(name string) error {
	if name == "" || name == "." || name == ".." ||
		strings.ContainsAny(name, `/\`+"\x00") || filepath.Base(name) != name {
		return status.Errorf(codes.InvalidArgument, "invalid file name %q", name)
	}
	return nil
}
