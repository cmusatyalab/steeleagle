package test

import (
	"context"

	pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1"
)

type controlServer struct {
	pb.UnimplementedControlServiceServer
}

func (i *controlServer) TakeOff(in *pb.TakeOffRequest, stream pb.ControlService_TakeOffServer) error {
	stream.Send(&pb.Response{})
	return nil
}

type missionServer struct {
	pb.UnimplementedMissionServiceServer
}

func (i *missionServer) Start(in *pb.StartRequest, stream pb.MissionService_StartServer) error {
	stream.Send(&pb.Response{})
	return nil
}

func (i *missionServer) Stop(in *pb.StopRequest, stream pb.MissionService_StopServer) error {
	stream.Send(&pb.Response{})
	return nil
}
