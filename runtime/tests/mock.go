package test

import (
    "context"

    pb "github.com/cmusatyalab/steeleagle/runtime/protos"
)

type controlServer struct {
    pb.UnimplementedControlServer
}

func (i *controlServer) Arm(_ context.Context, in *pb.ArmRequest) (*pb.Response, error) {
    return &pb.Response{Status: 2}, nil
}

func (i *controlServer) TakeOff(in *pb.TakeOffRequest, stream pb.Control_TakeOffServer) error {
    if err := stream.Send(&pb.Response{Status: 1}); err != nil {
        return err
    }
    stream.Send(&pb.Response{Status: 2})
    return nil
}

type missionServer struct {
    pb.UnimplementedMissionServer
}

func (i *missionServer) Start(_ context.Context, in *pb.StartRequest) (*pb.Response, error) {
    return &pb.Response{Status: 2}, nil
}

func (i *missionServer) Stop(_ context.Context, in *pb.StopRequest) (*pb.Response, error) {
    return &pb.Response{Status: 2}, nil
}
