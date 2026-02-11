package test

import (
    "context"
    "log/slog"

    "github.com/cmusatyalab/steeleagle/runtime/pb"
)

type controlServer struct {
    pb.UnimplementedControlServer
}

func (i *controlServer) Arm(_ context.Context, in *pb.ArmRequest) (*pb.Response, error) {
    slog.Info("received Arm request")
    return &pb.Response{Status: 2}, nil
}

func (i *controlServer) TakeOff(in *pb.TakeOffRequest, stream pb.Control_TakeOffServer) error {
    slog.Info("received TakeOff request")
    for i := 0; i < 2; i++ {
        slog.Info("sending in progress response")
        if err := stream.Send(&pb.Response{Status: 1}); err != nil {
            return err
        }
    }
    slog.Info("sending final completed response")
    stream.Send(&pb.Response{Status: 2})
    return nil
}

type missionServer struct {
    pb.UnimplementedControlServer
}

func (i *missionServer) Start(_ context.Context, in *pb.StartRequest) (*pb.Response, error) {
    slog.Info("reveived Start request")
    return &pb.Response{Status: 2}, nil
}
